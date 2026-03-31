# 模型设计方案

## 一、模型选型结论

**推荐：CatBoost 作为主模型 + Pi-Ratings 作为核心特征**

依据：arXiv:2309.14807 在 30万场比赛上的基准测试，这个组合在所有方法中表现最优，且工程复杂度合理。

---

## 二、整体架构

```
原始数据
  ├── 比赛结果历史（进失球、主客场）
  ├── 联赛排名数据
  ├── 球员阵容/伤病
  └── 赔率数据（可选，用于价值投注）
        ↓
   特征工程层
  ├── Pi-Ratings（动态评分）
  ├── 近期状态特征（近5/10场）
  ├── 主客场分别统计
  ├── 联赛上下文特征
  └── 赔率隐含概率（可选）
        ↓
   CatBoost 分类器
   输出：P(主胜), P(平), P(客胜)
        ↓
   后处理
  ├── 概率校准（Platt Scaling / Isotonic Regression）
  └── 价值投注信号 = 模型概率 - 庄家隐含概率
```

---

## 三、特征工程详解

### 3.1 Pi-Ratings（最重要的特征）

动态更新的球队进攻/防守评分：

```python
# 更新公式
k = 0.1  # 学习率
expected_diff = attack_home - defense_away + home_advantage
actual_diff = home_goals - away_goals

# 更新进攻评分
attack_home_new = attack_home + k * (actual_diff - expected_diff)
# 更新防守评分（失球反向更新）
defense_away_new = defense_away - k * (actual_diff - expected_diff)
```

产出特征：
- `pi_attack_home`, `pi_defense_home`
- `pi_attack_away`, `pi_defense_away`
- `pi_diff` = (attack_home - defense_away) - (attack_away - defense_home)

### 3.2 近期状态特征

```python
# 对每支球队，计算近 N 场（N=5, 10）
features = {
    'win_rate_5': 近5场胜率,
    'goal_scored_avg_5': 近5场场均进球,
    'goal_conceded_avg_5': 近5场场均失球,
    'clean_sheet_rate_5': 近5场零封率,
    'form_points_5': 近5场积分（胜3平1负0）,
    'home_win_rate_season': 本赛季主场胜率,
    'away_win_rate_season': 本赛季客场胜率,
}
```

### 3.3 对阵历史（Head-to-Head）

```python
h2h_features = {
    'h2h_home_win_rate': 历史主场队胜率（最近10次交锋）,
    'h2h_avg_goals': 历史场均进球,
    'h2h_btts_rate': 历史双方都进球概率,
}
```

### 3.4 联赛阶段特征

```python
context_features = {
    'season_progress': 赛季进度（0-1）,
    'home_league_position': 主队联赛排名,
    'away_league_position': 客队联赛排名,
    'position_diff': 排名差,
    'is_derby': 是否同城德比（哑变量）,
    'rest_days_home': 主队上场距今天数,
    'rest_days_away': 客队上场距今天数,
}
```

### 3.5 赔率特征（可选，大幅提升精度）

```python
odds_features = {
    'implied_prob_home': 1 / odds_home（去除水位后）,
    'implied_prob_draw': 1 / odds_draw,
    'implied_prob_away': 1 / odds_away,
    'market_efficiency': 水位大小（越小越准）,
}
```

> 注：国内体彩数据可从球探网/500彩票历史数据获取，赔率数据的加入通常将 RPS 提升 5-10%。

---

## 四、模型训练策略

### 时间切分（重要！）

```
训练集: T-∞ 到 T-90天
验证集: T-90天 到 T-30天（用于超参调整）
测试集: T-30天 到 T（模拟上线效果）
```

**绝对不能用未来数据训练**，必须严格按时间顺序切分。

### 超参数

```python
catboost_params = {
    'iterations': 1000,
    'learning_rate': 0.05,
    'depth': 6,
    'loss_function': 'MultiClass',
    'eval_metric': 'MultiClass',
    'early_stopping_rounds': 50,
    'cat_features': ['team_home', 'team_away', 'league'],
}
```

### 概率校准

CatBoost 输出的原始概率通常已较好校准，但建议用 `sklearn.calibration.CalibratedClassifierCV` 进一步校准，并绘制校准曲线验证。

---

## 五、评估指标

**主要指标：RPS（Ranked Probability Score）**

```python
def rps(probs, outcome):
    """
    probs: [p_home, p_draw, p_away]
    outcome: 0=home, 1=draw, 2=away
    """
    cum_probs = np.cumsum(probs)
    cum_actual = np.cumsum([1 if outcome == i else 0 for i in range(3)])
    return np.mean((cum_probs - cum_actual) ** 2)
```

**基准线：**
- 随机猜测：RPS ≈ 0.333
- 只用赔率：RPS ≈ 0.190-0.200
- 好的模型：RPS ≈ 0.195-0.210（接近但难超越赔率）

---

## 六、迭代路线图

### V1：Baseline
- Pi-Ratings + 近期状态特征
- CatBoost 三分类
- 中超/中甲历史数据回测

### V2：赔率融合
- 接入体彩赔率数据
- 价值投注信号输出
- 概率校准优化

### V3：深度特征
- 球员层面数据（阵容完整性、关键球员伤病）
- 赛季阶段权重（降组/争冠的动机调整）
- xG（预期进球）特征

### V4：实时预测（赛中）
- 实时比分 → 动态更新胜负概率
- WebSocket 推送
