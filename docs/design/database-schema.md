# Augur 数据库设计

> 设计原则：**换数据源不改 schema，Adapter 只改代码不动表**

## 整体架构：三层数据模型

```
Raw Data (来源原始格式)
    ↓ [Adapter: fivehundred / footballdata / ...]
Canonical Data (全项目通用格式)
    ↓ [Feature Pipeline]
Model Features (喂给模型的特征)
```

核心思路：把"数据源"当成一个**字段**而不是**表结构**。历史数据 + 实时数据 = 同一套表，用 `source` 字段区分来源。

---

## 表结构

### 1. `leagues` 联赛表

```sql
CREATE TABLE leagues (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(20)  NOT NULL UNIQUE,   -- PL, CL, BSA, 英超
    name_cn         VARCHAR(50),                     -- 中文名
    name_en         VARCHAR(50),                     -- 英文名
    country         VARCHAR(30),                     -- 所属国家
    source_config   JSONB,                           -- 爬虫配置 {season_format: "2024-25", ...}
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### 2. `teams` 球队主表（Canonical 格式，唯一数据源）

```sql
CREATE TABLE teams (
    id              SERIAL PRIMARY KEY,
    canonical_name  VARCHAR(100) NOT NULL,            -- 英文名 Arsenal
    league_code     VARCHAR(20) REFERENCES leagues(code),
    pi_attack       FLOAT DEFAULT 1000,
    pi_defense      FLOAT DEFAULT 1000,
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(canonical_name, league_code)
);
```

> **为什么 canonical_name 用英文？** 模型训练数据（football-data.org）本身是英文，500.com 是中文——英文作为主键，中文作为别名。这样无论哪个数据源，都用英文名关联。

### 3. `team_aliases` 球队别名表（关键！中文 ↔ 英文映射）

```sql
CREATE TABLE team_aliases (
    id              SERIAL PRIMARY KEY,
    team_id         INT REFERENCES teams(id) ON DELETE CASCADE,
    source          VARCHAR(30)  NOT NULL,            -- 'fivehundred' | 'footballdata' | 'titan007' ...
    alias           VARCHAR(100) NOT NULL,            -- 该数据源中的名字
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(source, alias)
);

-- 示例数据
-- (Arsenal, 'fivehundred', '阿森纳')
-- (Arsenal, 'footballdata', 'Arsenal')
-- (Arsenal, 'titan007',     '阿仙奴')
```

> **核心价值**：Adapter 只需查这张表就能把中文名转英文名，再用英文名关联 Canonical 表。新增数据源只需插入别名记录，不需要改任何代码。

### 4. `matches` 比赛主表（Canonical，训练/实时共用）

```sql
CREATE TABLE matches (
    id                  SERIAL PRIMARY KEY,
    canonical_home_id   INT REFERENCES teams(id),
    canonical_away_id   INT REFERENCES teams(id),
    league_code         VARCHAR(20) REFERENCES leagues(code),

    match_date          TIMESTAMP NOT NULL,           -- 比赛时间（UTC 或本地统一）
    home_goals          INT,
    away_goals          INT,
    status              VARCHAR(20) DEFAULT 'scheduled', -- scheduled | finished | cancelled

    -- 胜平负结果
    result              VARCHAR(10),                   -- home_win | draw | away_win | null

    source              VARCHAR(30)  NOT NULL,         -- 'fivehundred' | 'footballdata' ...
    source_match_id     VARCHAR(100),                  -- 数据源中的原始 ID

    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),

    UNIQUE(source, source_match_id)
);

CREATE INDEX idx_matches_date      ON matches(match_date);
CREATE INDEX idx_matches_league    ON matches(league_code);
CREATE INDEX idx_matches_status   ON matches(status);
CREATE INDEX idx_matches_canonical ON matches(canonical_home_id, canonical_away_id);
```

> **关键设计**：`canonical_home_id` / `canonical_away_id` 是外键指向 `teams` 的英文主键。任何数据源的中文名通过 `team_aliases` 查到 team_id，再关联到 canonical 格式。

### 5. `match_events` 比赛事件表

```sql
CREATE TABLE match_events (
    id              SERIAL PRIMARY KEY,
    match_id        INT REFERENCES matches(id) ON DELETE CASCADE,
    event_type      VARCHAR(20) NOT NULL,   -- goal | yellow_card | red_card | substitution
    minute          INT,
    team_id         INT REFERENCES teams(id),
    player_name     VARCHAR(100),
    detail          VARCHAR(50),            -- goal_type: normal / penalty / own_goal
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_events_match ON match_events(match_id);
```

### 6. `player_stats` 球员统计表

```sql
CREATE TABLE player_stats (
    id              SERIAL PRIMARY KEY,
    player_name     VARCHAR(100) NOT NULL,
    team_id         INT REFERENCES teams(id),
    league_code     VARCHAR(20),
    season          VARCHAR(10),           -- 2024-25
    match_id        INT REFERENCES matches(id),

    -- 基础统计
    appearances     INT DEFAULT 0,
    minutes         INT DEFAULT 0,
    goals           INT DEFAULT 0,
    assists         INT DEFAULT 0,
    yellow_cards    INT DEFAULT 0,
    red_cards       INT DEFAULT 0,
    shots           INT DEFAULT 0,
    shots_on_target INT DEFAULT 0,
    passes          INT DEFAULT 0,
    pass_accuracy   FLOAT DEFAULT 0,
    tackles         INT DEFAULT 0,
    interceptions   INT DEFAULT 0,
    fouls           INT DEFAULT 0,
    offsides        INT DEFAULT 0,
    saves           INT DEFAULT 0,         -- 门将
    clean_sheets    INT DEFAULT 0,          -- 门将

    source          VARCHAR(30) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(player_name, match_id, source)
);

CREATE INDEX idx_player_team  ON player_stats(team_id);
CREATE INDEX idx_player_match ON player_stats(match_id);
```

### 7. `odds_history` 赔率历史表（核心！历史+实时共用）

```sql
CREATE TABLE odds_history (
    id              SERIAL PRIMARY KEY,
    match_id        INT REFERENCES matches(id) ON DELETE CASCADE,
    source          VARCHAR(30) NOT NULL,         -- 'fivehundred' | 'footballdata' | 'pinnacle' ...

    -- 胜平负赔率
    odds_home       FLOAT,
    odds_draw       FLOAT,
    odds_away       FLOAT,

    -- 让球赔率（spf / handicap）
    handicap        FLOAT,                        -- 让球数，如 -1, +1
    odds_handicap_home  FLOAT,
    odds_handicap_away  FLOAT,

    -- 大小球
    total_line      FLOAT,                        -- 盘口线，如 2.5
    odds_over       FLOAT,
    odds_under      FLOAT,

    odds_type       VARCHAR(20) DEFAULT 'main',  -- 'main' | 'handicap' | 'total' | 'half'

    scraped_at      TIMESTAMP DEFAULT NOW(),     -- 爬取时间
    match_time      TIMESTAMP,                   -- 比赛时间（用于对比盘口变化）

    UNIQUE(match_id, source, odds_type, scraped_at)
);

CREATE INDEX idx_odds_match    ON odds_history(match_id);
CREATE INDEX idx_odds_scraped  ON odds_history(scraped_at);
CREATE INDEX idx_odds_source   ON odds_history(source);
```

> **统一赔率表的意义**：
> - 历史训练数据（footballdata）存进来 → 训练模型用
> - 实时数据（500.com）每小时更新存进来 → 实时信号用
> - 同一张表，不同 source，不同时间戳
> - 盘口变化可以做 line movement 分析

### 8. `predictions` 预测表

```sql
CREATE TABLE predictions (
    id                  SERIAL PRIMARY KEY,
    match_id            INT REFERENCES matches(id) ON DELETE CASCADE,
    model_name          VARCHAR(50) NOT NULL,      -- 'catboost_v1' | 'catboost_v2' ...

    pred_home_win       FLOAT NOT NULL,
    pred_draw           FLOAT NOT NULL,
    pred_away_win       FLOAT NOT NULL,

    pred_prob_sum       FLOAT,                     -- 验算：三个概率之和（应为1）
    confidence          FLOAT,                     -- 置信度

    -- 与市场对比（Value Betting 核心）
    implied_home        FLOAT,                     -- 市场隐含概率（从 odds_history 取最新赔率算）
    implied_draw       FLOAT,
    implied_away       FLOAT,

    value_home         FLOAT,                     -- pred - implied，正值=价值信号
    value_draw         FLOAT,
    value_away         FLOAT,

    predicted_at       TIMESTAMP DEFAULT NOW(),
    UNIQUE(match_id, model_name, predicted_at)
);

CREATE INDEX idx_pred_match ON predictions(match_id);
CREATE INDEX idx_pred_model  ON predictions(model_name);
```

### 9. `scrapers` 爬虫配置表

```sql
CREATE TABLE scrapers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50)  NOT NULL UNIQUE, -- 'fivehundred' | 'footballdata' | 'titan007'
    adapter_class   VARCHAR(100) NOT NULL,         -- 'FiveHundredAdapter' | 'FootballDataAdapter'
    base_url        TEXT,
    api_key         VARCHAR(200),                  -- 加密存储
    config          JSONB,                         -- 爬虫特定配置

    -- 调度配置
    schedule_type   VARCHAR(20) DEFAULT 'interval',  -- 'interval' | 'cron'
    schedule_value  VARCHAR(50),                    -- '3600'（秒）或 '0 6 * * *'（cron）
    enabled         BOOLEAN DEFAULT TRUE,
    last_run_at     TIMESTAMP,
    last_status     VARCHAR(20),                    -- 'success' | 'failed' | 'running'
    last_error      TEXT,

    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

### 10. `scraper_runs` 爬虫执行记录

```sql
CREATE TABLE scraper_runs (
    id              SERIAL PRIMARY KEY,
    scraper_name    VARCHAR(50) NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    status          VARCHAR(20) NOT NULL,         -- running | success | failed
    records_fetched INT DEFAULT 0,
    error_message   TEXT,
    duration_secs   FLOAT
);

CREATE INDEX idx_runs_name   ON scraper_runs(scraper_name);
CREATE INDEX idx_runs_started ON scraper_runs(started_at);
```

---

## 球队别名映射工作流

```
500.com 爬回: "阿森纳 vs 切尔西"
    ↓
Adapter 查询 team_aliases:
    "阿森纳" → fivehundred → team_id = 3 (Arsenal)
    "切尔西" → fivehundred → team_id = 7 (Chelsea)
    ↓
写入 matches:
    canonical_home_id = 3, canonical_away_id = 7
    source = 'fivehundred'
    source_match_id = '周四001'
```

---

## 新增数据源流程（无需改 schema）

**Step 1**：在 `team_aliases` 插入新数据源的别名映射

```sql
INSERT INTO team_aliases (team_id, source, alias)
SELECT id, 'titan007', alias_name
FROM teams, (VALUES
    ('Arsenal', '阿仙奴'),
    ('Chelsea', '車路士')
) AS mapping(canonical_name, alias_name)
WHERE teams.canonical_name = mapping.canonical_name;
```

**Step 2**：实现新的 Adapter class

```python
class Titan007Adapter(BaseAdapter):
    async def fetch_matches(self, date) -> List[Match]:
        # 爬 titan007，返回 Match dataclass（用 Canonical 格式）
        # 别名转换在 Adapter 内部通过 team_aliases 表做
        pass
```

**Step 3**：注册爬虫

```python
# 在 APScheduler 任务中
await db.execute("""
    INSERT INTO scrapers (name, adapter_class, schedule_type, schedule_value, enabled)
    VALUES ('titan007', 'Titan007Adapter', 'interval', '7200', TRUE)
    ON CONFLICT (name) DO UPDATE SET enabled = TRUE
""")
```

---

## 数据分层存储策略

| 数据类型 | 存储位置 | 保留时间 | 用途 |
|---------|---------|---------|------|
| 比赛结果（历史）| PostgreSQL `matches` | 永久 | 模型训练 |
| 赔率（历史）| PostgreSQL `odds_history` | 永久 | 训练 + 分析 |
| 球员统计（历史）| PostgreSQL `player_stats` | 永久 | 模型特征 |
| 当日赔率（实时）| PostgreSQL `odds_history` | 7天 | 实时 Value 信号 |
| 模型预测 | PostgreSQL `predictions` | 30天 | 分析回测 |
| 爬虫原始响应 | 原始 JSON 文件（可选存 OSS） | 3天 | Debug / 重放 |

---

## Schema 演进策略

> 数据源不确定 → schema 必须支持扩展而不破坏

1. **只加表、不改旧表**：新数据类型加新表，旧表不动
2. **JSONB 字段存变体数据**：每个 adapter 的特殊字段存在 `config` / `data` JSONB 列中，不污染主表
3. **source 字段隔离**：所有表都有 `source`，不同源数据物理隔离，查询时按 source 过滤
4. **Canonical 层不可逆**：Adapter 负责把数据转成 Canonical 格式存入，Canonical 层不感知来源差异
