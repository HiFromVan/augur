# 数据获取策略

## 一、数据需求清单

| 数据类型 | 用途 | 更新频率 | 优先级 |
|----------|------|----------|--------|
| 比赛结果（历史） | 模型训练 | 每场比赛后 | 必须 |
| 实时赛程 | 预测触发 | 每天 | 必须 |
| 联赛积分榜 | 排名特征 | 每轮后 | 必须 |
| 球队阵容/伤病 | 模型特征 | 每场前 | 重要 |
| 体彩赔率 | 价值投注信号 | 赛前实时 | 重要 |
| 球员统计 | V2 特征 | 每场后 | 可选 |
| 天气数据 | 辅助特征 | 赛前 | 可选 |

---

## 二、国内赛事数据源

### 2.1 免费数据源

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
- 用途：验证数据准确性

### 2.2 国际数据源（欧洲联赛）

**football-data.org**
- API 接口，免费版支持英超、西甲等主流联赛
- Python: `pip install football-data-api`
- 适合做欧洲联赛对比基准

**FBref（fbref.com）**
- 最详细的球员/球队统计，含 xG
- `soccerdata` 库封装了爬虫
- 中超数据较少

**Transfermarkt**
- 球员身价、转会、伤病历史
- `soccerdata` / `worldfootballR` 支持

### 2.3 付费数据源（V2 阶段考虑）

| 服务 | 价格 | 特点 |
|------|------|------|
| Opta / StatsPerform | 企业级 | 最完整，含中超 |
| API-Football | $15-50/月 | 性价比高，中超有覆盖 |
| StatsBomb | 学术免费 | 开放部分数据用于研究 |

---

## 三、数据采集架构

```
调度器（APScheduler / Celery Beat）
    ├── 每日任务：更新赛程、积分榜
    ├── 赛后任务：更新比赛结果，重新计算 Pi-Ratings
    ├── 赛前任务（T-24h）：抓取赔率、阵容
    └── 实时任务（比赛日）：更新赔率走势

数据存储
    ├── PostgreSQL：结构化历史数据（比赛、球队、球员）
    ├── Redis：热数据缓存（当日赛程、最新赔率）
    └── 文件存储：原始爬虫数据备份（JSON）
```

---

## 四、数据模型（核心表结构）

```sql
-- 球队表
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    league_id INT,
    pi_attack FLOAT DEFAULT 0,   -- 实时 Pi 进攻评分
    pi_defense FLOAT DEFAULT 0,  -- 实时 Pi 防守评分
    updated_at TIMESTAMP
);

-- 比赛表
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    home_team_id INT,
    away_team_id INT,
    league_id INT,
    match_date TIMESTAMP,
    home_goals INT,
    away_goals INT,
    status VARCHAR(20),   -- scheduled/finished/live
    -- 预测结果
    pred_home_win FLOAT,
    pred_draw FLOAT,
    pred_away_win FLOAT,
    -- 赔率（体彩）
    odds_home FLOAT,
    odds_draw FLOAT,
    odds_away FLOAT
);

-- Pi-Ratings 历史（每场比赛后快照）
CREATE TABLE pi_ratings_history (
    id SERIAL PRIMARY KEY,
    team_id INT,
    match_id INT,
    pi_attack FLOAT,
    pi_defense FLOAT,
    snapshot_date TIMESTAMP
);
```

---

## 五、冷启动问题

国内数据历史相对较短，建议：

1. **初始化 Pi-Ratings**：用历史 3-5 个赛季数据跑完整初始化
2. **借用欧洲数据预训练**：先在欧洲联赛数据上训练基础模型，再用中超数据 fine-tune
3. **回退策略**：数据不足时，退化为简单的主客场胜率 + 排名差，不输出概率

---

## 六、数据质量控制

- 结果异常检测：进球数 > 15 的比赛标记人工审核
- 赔率合理性检测：三项赔率隐含概率之和应在 1.0-1.15 之间（水位）
- 时间戳去重：爬虫重复抓取的去重逻辑
- 数据版本控制：记录每次数据更新来源，支持回滚
