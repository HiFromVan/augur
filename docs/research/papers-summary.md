# 关键论文观点整理

## 一、必读：2024 综述

### arXiv:2403.07669 — ML for Soccer Match Result Prediction (2024)

**结论摘要：**
- 梯度提升树（XGBoost, CatBoost, LightGBM）在结构化特征上持续优于深度学习
- 深度学习（LSTM, Transformer）在序列建模上有优势，但数据量要求高
- 混合方法（评分系统特征 + 梯度提升树）是目前最平衡的选择
- **关键发现**：特征质量 > 模型复杂度

**对我们的启示：** 不要过早上复杂模型，先用 CatBoost + 好特征建立 baseline。

---

## 二、最重要的基准论文

### arXiv:2309.14807 — Deep Learning & Gradient-Boosted Trees Benchmark (2023)

**数据集：** 2023 Soccer Prediction Challenge，300,000+ 场，51 个联赛

**核心结论：**
- **最佳组合：CatBoost + pi-ratings 特征**
- 深度学习在此数据集上未超越梯度提升树
- pi-ratings 特征是迄今最强的手工特征之一

**实验设置：**
- 训练集/测试集按时间切分（防止未来信息泄露）
- 评估指标：RPS（Ranked Probability Score），对概率预测更敏感

**对我们的启示：** 
- 用 RPS 而非 accuracy 评估模型
- pi-ratings 必须实现，是核心特征

---

## 三、核心特征体系

### Pi-Ratings — Constantinou & Fenton (2013)
*Journal of Quantitative Analysis in Sports*

**方法：**
- 基于进失球差动态更新球队评分
- 类似 Elo，但对比赛得分差更敏感（不只看胜负）
- 主客场分别维护评分
- 更新公式：`π_new = π_old + k * (actual_diff - expected_diff)`

**为什么强：**
- 捕捉球队近期状态变化
- 对大比分胜利给予合理奖励
- 计算简单，可实时更新

**实现参考：** 可直接参考 Constantinou 的原始论文公式实现，约 50 行 Python。

---

## 四、贝叶斯方法

### KDD 2019 — Pairwise Comparisons with Flexible Time-Dynamics
*Maystre, Kristof, Grossglauser (EPFL)*

**创新点：**
- 将球队技能建模为高斯过程（GP），自动学习「遗忘速度」
- 支持球员级别建模：球队技能 = f(在场球员技能)
- 处理伤病/转会等导致的技能突变

**局限：**
- 计算成本高（变分推断）
- 需要球员上场数据，国内赛事较难获取完整数据

---

## 五、复杂网络方法

### arXiv:2409.13098 — Soccer Matches with Complex Networks and ML (2024)

**方法：**
- 将球队传球关系建模为图
- 提取网络中心性、聚类系数等图特征
- 将图特征与传统统计特征融合进 ML 模型

**结论：** 图特征对进攻组织型球队（如 Barcelona 风格）识别效果好

**对我们的启示：** 在基础模型成熟后，可作为特征增强方向。国内暂时数据不够细，优先级低。

---

## 六、实时预测

### arXiv:2511.18730 — Large-Scale In-Game Outcome Forecasting (2025)

**规模：** 62,610 场，28 个联赛，9 个赛季

**方法：** 实时更新比赛内概率（根据当前比分、时间、球队状态）

**对我们的启示：** MVP 阶段做赛前预测，赛中实时预测是 V2 方向。

---

## 七、模型评估指标对比

| 指标 | 说明 | 适用场景 |
|------|------|----------|
| **RPS** (Ranked Probability Score) | 对有序概率预测最敏感 | 胜平负三分类，推荐主用 |
| **Log-Loss** | 对极端概率惩罚重 | 概率校准评估 |
| **Accuracy** | 只看最高概率对不对 | 直觉理解，但不适合评估概率质量 |
| **ROI** | 价值投注回报率 | 商业验证，需结合赔率 |
| **Brier Score** | 平方误差，可分解为校准+分辨率 | 模型诊断 |

**建议同时报告：** RPS + Calibration Curve（校准曲线），让用户看到模型概率是否可信。

---

## 八、一个重要教训（文献共识）

> 预测足球比赛天花板：单场比赛随机性极高，即使最好的模型 accuracy 也在 50-55% 区间（三分类）。
> 
> **正确的产品定位不是「预测对哪场」，而是「在大量预测中找到期望值为正的机会」。**

这就是为什么价值投注（Value Betting）视角比「准确率」更重要。
