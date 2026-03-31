# 开源模型盘点

## 一、可直接使用的引擎

### kickscore — 贝叶斯动态评分
- **仓库**：https://github.com/lucasmaystre/kickscore
- **安装**：`pip install kickscore`
- **原理**：
  - 每支球队（或球员）有一个随时间变化的技能分数
  - 技能变化用高斯过程建模（可选核函数：Wiener、Matern、Periodic 等）
  - 比赛结果 = 两队技能差的函数，用变分推断拟合
- **优势**：
  - 天然处理球队实力随赛季演变的问题
  - 输出概率分布而非点预测
  - 有论文支撑（KDD 2019）
- **局限**：需要较长历史数据才能收敛，冷启动困难

### footixify — 球员统计 ML
- **仓库**：https://github.com/Mg30/footixify
- **技术栈**：Python, FastAPI, Vue.js
- **模型**：基于球员统计特征的分类模型
- **特点**：包含价值投注扫描逻辑（对比庄家赔率），可直接参考工程结构

---

## 二、数据与特征参考

### fivethirtyeight/data — SPI 数据集
- **仓库**：https://github.com/fivethirtyeight/data/tree/master/soccer-spi
- **内容**：历史比赛预测概率、SPI 评分、实际结果
- **价值**：可以用来评估自己模型 vs 538 基准的差距

### DOsinga/football_predictions
- **仓库**：https://github.com/DOsinga/football_predictions
- **方法**：历史进球差分布 + 泊松模型模拟
- **适合**：理解概率预测基础，代码简洁易读

### msoczi/football_predictions
- **仓库**：https://github.com/msoczi/football_predictions
- **方法**：XGBoost + 球队近期状态特征
- **特点**：无需赔率数据，纯统计特征，适合国内场景（赔率数据不易获取）
- **特征**：近 N 场胜率、进失球均值、主客场分别统计

### mhaythornthwaite/Football_Prediction_Project
- **仓库**：https://github.com/mhaythornthwaite/Football_Prediction_Project
- **数据源**：api-football API
- **方法**：经典 ML 分类器（Random Forest, Logistic Regression 等）对比

---

## 三、技术架构对比

| 项目 | 数据源 | 特征类型 | 模型 | 输出 |
|------|--------|----------|------|------|
| kickscore | 比赛结果 | 时序技能评分 | Bayesian GP | 概率分布 |
| footixify | 球员统计 | 个人数据聚合 | ML 分类器 | 概率 + 价值信号 |
| msoczi | 历史比赛 | 球队状态 | XGBoost | 胜平负概率 |
| 538 SPI | 比赛结果 + 期望进球 | 进攻/防守 xG | 专有 | 概率 |

---

## 四、建议复用策略

针对国内市场，建议以下组合：

```
msoczi 的特征工程思路（球队状态特征）
    +
kickscore 的动态评分思路（pi-ratings 变体）
    +
footixify 的工程架构（FastAPI + Web 前端）
```

核心差异在于需要自建国内赛事数据 pipeline，这是最大的工作量。

---

## 五、数据获取开源工具

| 工具 | 说明 |
|------|------|
| `soccerdata` (Python) | 封装多个数据源：FBref, WhoScored, ESPN 等 |
| `football-data-api` | football-data.org 的 Python 客户端，免费版支持主流欧洲联赛 |
| `worldfootballR` (R) | FBref/Transfermarkt 数据，R 语言 |
| 自建爬虫 | 中超数据需针对雷速/球探等国内网站定制 |
