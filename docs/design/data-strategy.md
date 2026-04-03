# 数据获取策略

## 一、数据分层架构

数据、特征、模型三层分离，互不耦合：

```
原始数据层（Raw）     → 采集时不管模型要什么，存一切
      ↓
特征层（Features）    → 统一特征仓库，所有模型从这里取
      ↓
模型层（Models）      → 标准接口，换模型不动上下两层
```

**核心原则：** 爬虫只管抓原始数据，不筛选字段。特征计算独立进行，模型只消费特征，不直接碰原始数据。

---

## 二、数据需求清单（按信噪比排序）

### 第一档：必采，信号强

| 数据类型 | 用途 | 更新频率 | 说明 |
|----------|------|----------|------|
| 比赛结果（历史） | 模型训练核心 | 每场后 | 没有就没有一切 |
| **赔率数据** | **价值投注信号 + 模型特征** | **赛前实时** | 市场已隐含伤病/舆情/盘口动向，单靠赔率 RPS 可达 0.195，优先级升为必须 |
| 实时赛程 | 预测触发 | 每天 | — |
| 联赛积分榜 | 排名特征 | 每轮后 | — |

### 第二档：值得采，需要处理

| 数据类型 | 用途 | 更新频率 | 说明 |
|----------|------|----------|------|
| 首发阵容 | 轮换信号 | 赛前 | 是否大规模轮换影响显著 |
| 确认缺阵球员 | 关键球员缺阵特征 | 赛前 | 只采官方确认缺阵，不采"疑似"传言 |
| 主客场疲劳指标 | 体力特征 | 赛前计算 | 用比赛间隔天数代替，无需额外数据源 |
| 球员统计 | V2 特征扩展 | 每场后 | — |

### 第三档：谨慎采，验证后再用

| 数据类型 | 说明 |
|----------|------|
| 天气数据 | 理论有用，实际信号微弱；室内场馆无关；V3 验证后再决定是否保留 |
| 媒体文本 / 舆情 | 有真实信号（赛前发布会、官方伤病通报），但需要 LLM 结构化提取，国内数据质量参差，V3 再做 |
| xG 数据 | FBref 有覆盖但中超较少，V3 阶段接入 |

---

## 三、国内赛事数据源

### 3.1 免费数据源

**雷速体育（leisu.com）**
- 覆盖：中超、中甲、中乙、亚冠
- 内容：比赛结果、积分榜、球员数据
- 获取方式：页面爬虫（反爬中等难度）
- 注意：遵守 robots.txt，控制频率

**球探网（jczq.com / zq.titan007.com）**
- 覆盖：全球联赛，中超完整
- 内容：**赔率走势**（最有价值），比赛结果，指数对比
- 历史数据：可追溯到 2000 年左右
- 特点：亚盘、欧赔、大小球三类赔率都有

**500彩票（500.com）**
- 内容：体彩竞彩赔率，比赛数据
- 特点：国内体彩官方对接，赔率数据最接近实际投注环境

**中国足球协会官网 / 中超官网**
- 内容：官方比赛数据，但更新慢
- 用途：验证数据准确性；官方伤病/停赛通报

### 3.2 国际数据源（欧洲联赛）

**football-data.org**
- API 接口，免费版支持英超、西甲等主流联赛
- 适合做欧洲联赛对比基准

**FBref（fbref.com）**
- 最详细的球员/球队统计，含 xG
- `soccerdata` 库封装了爬虫
- 中超数据较少

**Transfermarkt**
- 球员身价、转会、伤病历史
- `soccerdata` / `worldfootballR` 支持

### 3.3 付费数据源（V2 阶段考虑）

| 服务 | 价格 | 特点 |
|------|------|------|
| Opta / StatsPerform | 企业级 | 最完整，含中超 |
| API-Football | $15-50/月 | 性价比高，中超有覆盖 |
| StatsBomb | 学术免费 | 开放部分数据用于研究 |

---

## 四、数据采集架构

```
调度器（APScheduler）
    ├── 每日任务：更新赛程、积分榜
    ├── 赛后任务：更新比赛结果，触发特征重计算
    ├── 赛前任务（T-24h）：抓取赔率、首发阵容、确认缺阵
    └── 实时任务（比赛日）：更新赔率走势

数据存储
    ├── PostgreSQL：原始数据 + 特征仓库 + 预测结果（分表）
    ├── Redis：热数据缓存（当日赛程、最新赔率）
    └── 文件存储：原始爬虫数据备份（JSON）
```

---

## 五、数据库表结构

### 5.1 原始数据层 — 只存，不计算

```sql
-- 爬虫原始数据，JSONB 存全量，不筛选字段
CREATE TABLE raw_match_events (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50),           -- 'leisu', 'titan007', '500'
    source_match_id VARCHAR(50),  -- 数据源自己的 ID
    raw_data JSONB,               -- 完整原始 JSON
    fetched_at TIMESTAMP,
    is_processed BOOLEAN DEFAULT FALSE
);
```

**原则：** 字段不够用时不改表结构，直接加进 JSONB。支持回溯重新计算特征。

### 5.2 结构化层 — 清洗后的标准数据

```sql
-- 球队表
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    league_id INT,
    pi_attack FLOAT DEFAULT 0,
    pi_defense FLOAT DEFAULT 0,
    updated_at TIMESTAMP
);

-- 比赛表（只存事实，不存预测）
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    home_team_id INT,
    away_team_id INT,
    league_id INT,
    match_date TIMESTAMP,
    home_goals INT,
    away_goals INT,
    status VARCHAR(20),    -- scheduled / finished / live
    odds_home FLOAT,
    odds_draw FLOAT,
    odds_away FLOAT
);

-- Pi-Ratings 历史快照
CREATE TABLE pi_ratings_history (
    id SERIAL PRIMARY KEY,
    team_id INT,
    match_id INT,
    pi_attack FLOAT,
    pi_defense FLOAT,
    snapshot_date TIMESTAMP
);
```

### 5.3 特征仓库 — 所有模型共用

```sql
-- 每场比赛 × 每个特征版本，存一行
CREATE TABLE match_features (
    match_id INT,
    feature_version VARCHAR(20),  -- 'v1', 'v1_with_odds', 'v2_with_lineup'
    features JSONB,               -- 所有特征的 key-value
    computed_at TIMESTAMP,
    PRIMARY KEY (match_id, feature_version)
);
```

### 5.4 预测结果 — 按模型版本隔离

```sql
-- 按模型版本分别存，支持对比和 A/B 测试
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    match_id INT,
    model_name VARCHAR(50),       -- 'catboost_v1', 'catboost_v2'
    pred_home_win FLOAT,
    pred_draw FLOAT,
    pred_away_win FLOAT,
    value_bet_signal FLOAT,       -- 模型概率 - 赔率隐含概率
    predicted_at TIMESTAMP
);
```

---

## 六、V3：媒体文本数据管道（待实现）

当基础模型 RPS 稳定后，考虑加入文本信号：

```
有价值的信号：
  ✓ 官方伤病通报（"X 号球员大腿拉伤，本轮缺阵"）
  ✓ 主教练赛前发布会（"我们会轮换"）
  ✓ 关键球员赛前训练状态报道

噪声（不采）：
  ✗ 球迷/媒体情绪
  ✗ 球员社媒互动量
  ✗ 未经证实的传言

处理管道：
  媒体文章 → LLM 提取 → 结构化事件 → 注入特征仓库
  {player: "武磊", event_type: "injury", severity: "minor", match_impact: "questionable"}
```

---

## 七、冷启动问题

1. **初始化 Pi-Ratings**：用历史 3-5 个赛季数据跑完整初始化
2. **借用欧洲数据预训练**：先在欧洲联赛数据上训练基础模型，再用中超数据 fine-tune
3. **回退策略**：数据不足时，退化为简单的主客场胜率 + 排名差，不输出概率

---

## 八、数据质量控制

- 结果异常检测：进球数 > 15 的比赛标记人工审核
- 赔率合理性检测：三项赔率隐含概率之和应在 1.0-1.15 之间（水位）
- 时间戳去重：爬虫重复抓取的去重逻辑
- 数据版本控制：记录每次数据更新来源，支持回滚