# 系统架构设计

## 一、系统全景

用户看到的不是"预测结果"，而是**一条价值投注信号 + 实时信息**。

```
用户打开 App
      ↓
查看今日赛事列表
      ↓
点进某场比赛
      ↓
看到：
  - 基础信息（排名、历史战绩、近5场状态）
  - 模型预测概率
  - 赔率 + 隐含概率
  - Value Bet 信号（模型 vs 市场差值）
  - 最新相关新闻（LLM 提取的伤病/阵容信号）
      ↓
用户做出判断
```

**核心逻辑：** 用户不是在买"预测"，是在买"信息整合"——模型概率、市场赔率、新闻信号，三个东西放在一起，让他自己判断。

---

## 二、数据层架构（三层分离）

```
原始数据层（Raw）       爬虫采集，JSONB 存全量
       ↓
特征层（Features）      计算好的特征，版本化管理
       ↓
模型层（Models）        训练 + 推理，标准接口
       ↓
用户交互层（API）       给前端提供实时数据
```

---

## 三、爬虫层设计

### 3.1 爬虫职责：只管抓，不管用

每个爬虫是独立的，抓完直接写原始数据表，不做清洗：

```sql
-- 原始数据表，只存 raw_data
CREATE TABLE raw_match_events (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50),          -- 'leisu', 'titan007', '500'
    source_type VARCHAR(20),     -- 'match', 'odds', 'news', 'lineup'
    source_match_id VARCHAR(50),
    raw_data JSONB,              -- 完整原始 JSON，不筛选
    fetched_at TIMESTAMP,
    is_processed BOOLEAN DEFAULT FALSE
);
```

**原则：** 爬虫只管抓 raw_data 写进去。字段不够用时不改表结构，往 JSONB 里加。

### 3.2 爬虫分类

| 爬虫 | 触发时机 | 写入 source_type | 说明 |
|------|----------|------------------|------|
| 赛程爬虫 | 每日 8:00 | `match` | 未来7天赛程 |
| 赔率爬虫 | 每30分钟 | `odds` | 赛前实时赔率 |
| 比赛结果爬虫 | 赛后30分钟 | `match` | 更新比分 |
| 阵容爬虫 | 赛前24h / 赛前2h | `lineup` | 首发阵容 |
| 伤病爬虫 | 每日 | `news` | 伤病/停赛信息 |
| 新闻爬虫 | 每小时 | `news` | 赛前相关报道 |

### 3.3 爬虫调度

```
APScheduler（嵌入 FastAPI 进程，不单独部署 Celery）
    ├── 每日 08:00：赛程 + 积分榜
    ├── 每30分钟：赔率（比赛日加密，比赛前2小时每15分钟一次）
    ├── 赛后30分钟：比赛结果
    ├── 赛前24h：阵容初版
    ├── 赛前2h：阵容最终版
    └── 每小时：新闻

Redis 缓存当日抓取状态，防止重复抓取
```

---

## 四、存储层设计

### 4.1 表结构

```sql
-- 球队（从 raw_match_events 清洗写入）
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    league_id INT,
    pi_attack FLOAT DEFAULT 0,
    pi_defense FLOAT DEFAULT 0,
    updated_at TIMESTAMP
);

-- 比赛（只存事实，预测结果另表存储）
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    home_team_id INT,
    away_team_id INT,
    league_id INT,
    match_date TIMESTAMP,
    home_goals INT,
    away_goals INT,
    status VARCHAR(20),   -- scheduled / live / finished
    -- 赔率（从 raw_odds_events 清洗写入）
    odds_home FLOAT,
    odds_draw FLOAT,
    odds_away FLOAT,
    odds_fetched_at TIMESTAMP
);

-- 特征仓库（所有模型共用）
CREATE TABLE match_features (
    match_id INT,
    feature_version VARCHAR(20),  -- 'v1', 'v2', 'v2_with_lineup'
    features JSONB,               -- key-value 特征
    computed_at TIMESTAMP,
    PRIMARY KEY (match_id, feature_version)
);

-- 模型预测结果（按模型版本隔离）
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    match_id INT,
    model_name VARCHAR(50),
    pred_home_win FLOAT,
    pred_draw FLOAT,
    pred_away_win FLOAT,
    predicted_at TIMESTAMP
);

-- 新闻事件（LLM 提取后写入）
CREATE TABLE news_events (
    id SERIAL PRIMARY KEY,
    match_id INT,
    player VARCHAR(100),
    event_type VARCHAR(50),   -- 'injury', 'lineup', 'transfer', 'suspension'
    severity VARCHAR(20),     -- 'confirmed', 'doubtful', 'rumor'
    content TEXT,             -- 原始新闻摘要
    llm_extracted_at TIMESTAMP
);

-- 用户交互（可选，V2）
CREATE TABLE user_bets (
    id SERIAL PRIMARY KEY,
    user_id INT,
    match_id INT,
    selected_outcome VARCHAR(20),
    odds_taken FLOAT,
    stake FLOAT,
    created_at TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE
);
```

### 4.2 缓存策略

```sql
-- Redis TTL 设计
当日赛程列表    → TTL 1h（每日8点刷新）
最新赔率        → TTL 5min（赔率变化快）
当前预测结果    → TTL 30min（赛前2小时加密刷新）
LLM 提取的新闻  → TTL 1h（赛前每小时更新）
```

**用户请求优先读 Redis，miss 了再查 PostgreSQL。**

---

## 五、模型推理架构

### 5.1 在线推理流程

```
比赛日 T-2h
      ↓
触发预测管道
      ↓
1. 从 raw_match_events 读取最新赔率 + 阵容
2. 写入 match_features（feature_version = 当前活跃版本）
3. 模型 predict() → predictions 表
4. 计算 Value Bet 信号：
   signal_home = pred_home_win - implied_prob_home
5. LLM 提取 news_events → 生成新闻摘要
6. 结果写入 Redis（TTL = 比赛开始）
      ↓
用户打开 App → 从 Redis 直接返回（< 50ms）
```

### 5.2 模型接口标准

```python
from abc import ABC, abstractmethod

class BasePredictor(ABC):
    @abstractmethod
    def predict(self, features: dict) -> dict:
        """输入特征，返回 {home_win, draw, away_win}"""
        pass

    @abstractmethod
    def required_features(self) -> list[str]:
        """声明需要哪些特征 key"""
        pass

    @abstractmethod
    def feature_version(self) -> str:
        """这个模型依赖哪个特征版本"""
        pass
```

### 5.3 模型注册与切换

```python
# model_registry.py
MODEL_REGISTRY = {
    'catboost_v1': CatBoostPredictor('models/catboost_v1.cbm'),
    'lstm_v1':     LSTMPredictor('models/lstm_v1.pt'),
}

ACTIVE_MODEL = 'catboost_v1'  # 改这个字符串就切换
```

**换模型流程：** 训练新模型 → 写入 models/ 目录 → 改配置 → 重启服务。不动数据，不动特征，不动 API。

### 5.4 离线训练流程

```
每次新数据积累到一定量（每赛季结束后，或每月）
      ↓
触发训练管道（Celery task 或 独立脚本）
      ↓
1. 从 match_features 读取历史特征
2. 从 matches 读取历史结果
3. 时间切分：训练 / 验证 / 测试
4. 训练 → 输出模型文件
5. 计算测试集 RPS，对比 ACTIVE_MODEL
6. RPS 更好 → 自动写入 model_registry（新版本）
7. MLflow 记录每次实验
```

---

## 六、LLM 新闻管道（V3）

### 6.1 数据来源

新闻爬虫采集以下内容：
- 球队官方公告（伤病、停赛）
- 主教练赛前发布会记录
- 权威体育媒体赛前报道（懂球帝、虎扑、中超官网）

### 6.2 处理流程

```
原始新闻文本
      ↓
LLM 提取（Claude API）
      ↓
结构化事件：
{
  "match_id": 12345,
  "player": "武磊",
  "event_type": "injury",
  "severity": "confirmed",
  "match_impact": "key_player_missing",
  "summary": "官方确认武磊大腿拉伤，缺阵2周"
}
      ↓
写入 news_events 表
      ↓
注入 match_features 作为额外特征
      ↓
重新运行预测管道
```

### 6.3 新闻信号注入方式

新闻不直接改变概率，而是作为**特征权重调整**：

```python
# 例：新闻信号如何影响特征
news_signal = {
    'home_key_player_missing': 1,   # 主队核心缺阵
    'away_injury_rumors': 0,        # 客队只是传言
    'home_rotation_intended': 1,    # 主教练说会轮换
}

# 在特征层面调整
if news_signal['home_key_player_missing']:
    effective_pi_attack_home *= 0.85  # 降权
```

### 6.4 新闻质量过滤

| 信号类型 | 可信度 | 处理方式 |
|----------|--------|----------|
| 官方公告 | 高 | 直接使用 |
| 主教练发布会 | 中 | LLM 判断可信度 |
| 媒体报道 | 低 | 仅作为补充信号 |
| 球迷论坛/传言 | 噪声 | 直接丢弃 |

---

## 七、用户交互 API

### 7.1 核心接口

```
GET /api/matches?date=2026-04-05
→ 当日比赛列表（基础信息 + 预测 + 赔率 + Value 信号）

GET /api/matches/{match_id}
→ 比赛详情
   - 基础信息（排名、历史战绩）
   - 模型预测概率
   - 赔率 + 隐含概率
   - Value Bet 信号（按选项分别显示）
   - 最新新闻摘要（LLM 生成）

GET /api/matches/{match_id}/odds
→ 赔率走势（历史曲线）

GET /api/teams/{team_id}
→ 球队详情 + Pi-Ratings 曲线 + 近期状态

GET /api/models/compare?match_id=xxx
→ 各模型预测对比（如果有多个模型在线）
```

### 7.2 用户看到的数据来自哪些表

```
用户请求 /api/matches/{match_id}
      ↓
查 Redis（TTL 5min）
  命中 → 直接返回
  未命中 → 查 PostgreSQL 组装
      ↓
组装数据来源：
  matches 表         → 基础信息
  predictions 表     → 模型预测概率（ACTIVE_MODEL 版本）
  matches.odds_*     → 赔率
  news_events 表     → 最新新闻摘要（LLM 整理）
      ↓
返回 JSON
```

**爬虫数据和用户数据复用的逻辑：** 爬虫 raw → 清洗 → 写入对应表（matches, predictions, news_events）→ 用户 API 读这些表。同一份数据，只经过清洗和计算，供所有使用方消费。

---

## 八、完整数据流

```
[爬虫层]
  赛程/赔率/新闻/阵容
       ↓ raw_match_events
[清洗层]
  定时任务把 raw 写入结构化表
       ↓ matches / news_events
[特征层]
  定时任务计算特征 → match_features
       ↓
[模型层]
  推理管道读取特征 → predictions
  LLM 读取新闻 → news_events
       ↓
[缓存层]
  结果写入 Redis（TTL = 比赛开始）
       ↓
[API层]
  用户请求 → Redis → 返回
```

---

## 九、部署架构

```
单台服务器（V1-V2）
┌──────────────────────────────────┐
│  FastAPI (Gunicorn + Uvicorn workers)
│    ├── API 服务（给前端）
│    └── Scheduler（APScheduler 定时任务）
│
│  ML 推理：FastAPI 进程内调用（< 10ms）
│  ML 训练：Celery Worker（后台异步）
│
│  PostgreSQL（主库）
│  Redis（缓存）
│  MLflow（实验追踪，Docker）
└──────────────────────────────────┘
```

---

## 十、开发顺序

```
Phase 1（4周）：爬虫 + 基础数据
  - 赛程爬虫（leisu）
  - 赔率爬虫（titan007）
  - 历史数据入库
  - PostgreSQL 建表
  - 特征计算（Pi-Ratings + 近期状态）

Phase 2（3周）：模型 + 推理
  - CatBoost 训练 + 回测
  - 推理管道
  - 预测结果写入 + Redis 缓存
  - Value Bet 信号计算

Phase 3（2周）：API + 前端
  - FastAPI 接口
  - Next.js 比赛列表 + 详情页
  - 移动端适配

Phase 4（V3）：新闻 + LLM
  - 新闻爬虫
  - LLM 提取结构化事件
  - 新闻特征注入
  - 模型重新训练
```