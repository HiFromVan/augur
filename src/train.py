# 特征工程 + 模型训练脚本

import asyncio
import os
import json
import numpy as np
from datetime import datetime
from collections import defaultdict

from src.data import Database
from src.models import CatBoostPredictor


DATABASE_URL = "postgresql://augur:augur@localhost:5432/augur"
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")


def compute_pi_ratings(matches: list) -> dict:
    """计算 Pi-Ratings（进攻和防守评分）"""
    ratings = defaultdict(lambda: {'attack': 0.0, 'defense': 0.0})
    k = 0.05
    home_adv = 0.25

    sorted_matches = sorted(matches, key=lambda x: x['date'])

    for match in sorted_matches:
        if match['home_goals'] is None:
            continue

        home = match['home_team']
        away = match['away_team']
        hg = float(match['home_goals'])
        ag = float(match['away_goals'])

        # 预期进球 = 进攻 + 主场优势 - 对方防守
        expected_home = ratings[home]['attack'] + home_adv - ratings[away]['defense']
        expected_away = ratings[away]['attack'] - ratings[home]['defense']

        err_home = hg - expected_home
        err_away = ag - expected_away

        # 进攻：进球比预期多则提升
        ratings[home]['attack'] += k * err_home
        ratings[away]['attack'] += k * err_away

        # 防守：失球比预期少则提升（方向相反）
        ratings[home]['defense'] -= k * err_away
        ratings[away]['defense'] -= k * err_home

    return {k: dict(v) for k, v in ratings.items()}


def build_team_index(matches: list) -> dict:
    """预建球队比赛索引（按日期排序），避免 O(n²) 遍历"""
    from collections import defaultdict
    index = defaultdict(list)
    for m in matches:
        if m['home_goals'] is not None:
            index[m['home_team']].append(m)
            index[m['away_team']].append(m)
    # 每支球队按日期排序
    for team in index:
        index[team].sort(key=lambda x: x['date'])
    return dict(index)


def build_h2h_index(matches: list) -> dict:
    """预建交锋历史索引"""
    from collections import defaultdict
    index = defaultdict(list)
    for m in matches:
        if m['home_goals'] is not None:
            key = tuple(sorted([m['home_team'], m['away_team']]))
            index[key].append(m)
    for key in index:
        index[key].sort(key=lambda x: x['date'])
    return dict(index)


def _recent_form(team_name: str, match_date, team_index: dict, n=5):
    ms = team_index.get(team_name, [])
    import bisect
    dates = [m['date'] for m in ms]
    idx = bisect.bisect_left(dates, match_date)
    recent = ms[max(0, idx - n):idx]
    if not recent:
        return 0.33, 1.0, 1.0, 1.0
    wins = draws = goals_s = goals_c = 0
    for m in recent:
        is_home = m['home_team'] == team_name
        tg = m['home_goals'] if is_home else m['away_goals']
        og = m['away_goals'] if is_home else m['home_goals']
        goals_s += tg
        goals_c += og
        if tg > og:
            wins += 1
        elif tg == og:
            draws += 1
    total = len(recent)
    return wins / total, goals_s / total, goals_c / total, (wins * 3 + draws) / total


def _away_draw_rate(team_name: str, match_date, team_index: dict, n=5) -> float:
    """客队近n场客场平局率"""
    ms = team_index.get(team_name, [])
    import bisect
    dates = [m['date'] for m in ms]
    idx = bisect.bisect_left(dates, match_date)
    away_matches = [m for m in ms[max(0, idx - n * 2):idx] if m['away_team'] == team_name][-n:]
    if not away_matches:
        return 0.25
    draws = sum(1 for m in away_matches if m['home_goals'] == m['away_goals'])
    return draws / len(away_matches)


def _h2h(home_t: str, away_t: str, match_date, h2h_index: dict, n=10):
    key = tuple(sorted([home_t, away_t]))
    ms = h2h_index.get(key, [])
    import bisect
    dates = [m['date'] for m in ms]
    idx = bisect.bisect_left(dates, match_date)
    recent = ms[max(0, idx - n):idx]
    if not recent:
        return 0.33, 0.0, 2.5
    hw = sum(1 for m in recent if m['home_goals'] > m['away_goals'])
    dr = sum(1 for m in recent if m['home_goals'] == m['away_goals'])
    gl = sum(m['home_goals'] + m['away_goals'] for m in recent) / len(recent)
    return (hw + dr * 0.5) / len(recent), dr / len(recent), gl


def build_features(match: dict, pi_ratings: dict,
                   team_index: dict, h2h_index: dict, league_stats: dict = None) -> dict:
    """构建一场比赛的特征"""
    home = match['home_team']
    away = match['away_team']
    match_date = match['date']

    # Pi-Ratings
    hr = pi_ratings.get(home, {'attack': 1000, 'defense': 1000})
    ar = pi_ratings.get(away, {'attack': 1000, 'defense': 1000})
    pi_diff = (hr['attack'] - ar['defense']) - (ar['attack'] - hr['defense'])

    hw, hs, hc, hp = _recent_form(home, match_date, team_index)
    aw, a_s, a_c, ap = _recent_form(away, match_date, team_index)
    h2h_rate, h2h_draw, h2h_goals = _h2h(home, away, match_date, h2h_index)
    away_draw_rate = _away_draw_rate(away, match_date, team_index)

    # 赔率隐含概率（去除水位后）
    implied_home = implied_draw = implied_away = 1/3
    if match.get('odds_home') and match.get('odds_draw') and match.get('odds_away'):
        ih = 1 / match['odds_home']
        id_ = 1 / match['odds_draw']
        ia = 1 / match['odds_away']
        total = ih + id_ + ia
        implied_home = ih / total
        implied_draw = id_ / total
        implied_away = ia / total

    return {
        'pi_attack_home': hr['attack'],
        'pi_defense_home': hr['defense'],
        'pi_attack_away': ar['attack'],
        'pi_defense_away': ar['defense'],
        'pi_diff': pi_diff,
        'home_advantage': 0.25,
        'league': match.get('league', 'unknown'),
        'win_rate_home_5': hw,
        'goals_scored_home_5': hs,
        'goals_conceded_home_5': hc,
        'points_home_5': hp,
        'win_rate_away_5': aw,
        'goals_scored_away_5': a_s,
        'goals_conceded_away_5': a_c,
        'points_away_5': ap,
        'h2h_win_rate': h2h_rate,
        'h2h_draw_rate': h2h_draw,
        'h2h_avg_goals': h2h_goals,
        # 赔率特征（市场信息）
        'implied_home': implied_home,
        'implied_draw': implied_draw,
        'implied_away': implied_away,
        'odds_home': match.get('odds_home') or 0.0,
        'odds_draw': match.get('odds_draw') or 0.0,
        'odds_away': match.get('odds_away') or 0.0,
        # 亚盘特征
        'asian_home': match.get('odds_asian_home') or 0.0,
        'asian_away': match.get('odds_asian_away') or 0.0,
        # 大小球
        'ou_line': match.get('odds_ou_line') or 0.0,
        'ou_over': match.get('odds_ou_over') or 0.0,
        'ou_under': match.get('odds_ou_under') or 0.0,
        # 联赛平均进球特征
        'league_avg_home_goals': (league_stats or {}).get(match.get('league', ''), {}).get('avg_home') or (league_stats or {}).get('__global__', {}).get('avg_home', 1.36),
        'league_avg_away_goals': (league_stats or {}).get(match.get('league', ''), {}).get('avg_away') or (league_stats or {}).get('__global__', {}).get('avg_away', 1.18),
        'league_avg_total_goals': (league_stats or {}).get(match.get('league', ''), {}).get('avg_total') or (league_stats or {}).get('__global__', {}).get('avg_total', 2.54),
        'league_draw_rate': (league_stats or {}).get(match.get('league', ''), {}).get('draw_rate') or (league_stats or {}).get('__global__', {}).get('draw_rate', 0.25),
        'away_draw_rate_5': away_draw_rate,
    }


def build_league_stats(matches: list) -> dict:
    """预计算每个联赛的历史平均进球数和平局率"""
    from collections import defaultdict
    stats = defaultdict(lambda: {'home_goals': [], 'away_goals': [], 'draws': 0, 'total': 0})
    for m in matches:
        if m['home_goals'] is not None and m['away_goals'] is not None:
            league = m.get('league', 'unknown')
            stats[league]['home_goals'].append(m['home_goals'])
            stats[league]['away_goals'].append(m['away_goals'])
            stats[league]['total'] += 1
            if m['home_goals'] == m['away_goals']:
                stats[league]['draws'] += 1
    result = {}
    global_home = np.mean([m['home_goals'] for m in matches if m['home_goals'] is not None])
    global_away = np.mean([m['away_goals'] for m in matches if m['away_goals'] is not None])
    global_draws = sum(1 for m in matches if m['home_goals'] is not None and m['home_goals'] == m['away_goals'])
    global_total = sum(1 for m in matches if m['home_goals'] is not None)
    global_draw_rate = global_draws / global_total if global_total > 0 else 0.25
    for league, data in stats.items():
        draw_rate = data['draws'] / data['total'] if data['total'] > 0 else global_draw_rate
        result[league] = {
            'avg_home': np.mean(data['home_goals']) if data['home_goals'] else global_home,
            'avg_away': np.mean(data['away_goals']) if data['away_goals'] else global_away,
            'avg_total': np.mean([h + a for h, a in zip(data['home_goals'], data['away_goals'])]),
            'draw_rate': draw_rate,
        }
    result['__global__'] = {
        'avg_home': global_home, 'avg_away': global_away,
        'avg_total': global_home + global_away, 'draw_rate': global_draw_rate,
    }
    return result


async def main():
    print("=" * 50)
    print("Augur - 特征工程 + 模型训练")
    print("=" * 50)

    db = Database(DATABASE_URL)
    await db.connect()

    # 获取所有已完赛比赛
    matches = await db.get_matches(status='finished')
    print(f"Loaded {len(matches)} finished matches")

    # 按日期排序
    matches.sort(key=lambda x: x['date'])

    # 计算 Pi-Ratings
    print("\nComputing Pi-Ratings...")
    pi_ratings = compute_pi_ratings(matches)
    print(f"Computed ratings for {len(pi_ratings)} teams")

    # 打印部分球队评分
    print("\nSample team ratings (EPL):")
    epl_teams = ['Arsenal FC', 'Manchester City FC', 'Liverpool FC',
                 'Chelsea FC', 'Manchester United FC', 'Tottenham Hotspur FC']
    for team in epl_teams:
        if team in pi_ratings:
            r = pi_ratings[team]
            print(f"  {team}: attack={r['attack']:.1f}, defense={r['defense']:.1f}")

    # 预建索引
    print("\nBuilding indexes...")
    team_index = build_team_index(matches)
    h2h_index = build_h2h_index(matches)
    league_stats = build_league_stats(matches)
    print(f"Team index: {len(team_index)} teams, {len(league_stats)-1} leagues")

    # 构建特征
    print("\nBuilding features...")
    X = []
    y = []
    dates = []

    for i, match in enumerate(matches):
        features = build_features(match, pi_ratings, team_index, h2h_index, league_stats)

        # 标签
        if match['home_goals'] > match['away_goals']:
            label = 0
        elif match['home_goals'] == match['away_goals']:
            label = 1
        else:
            label = 2

        X.append(features)
        y.append(label)
        dates.append(str(match['date'])[:10])

        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(matches)}")

    print(f"Built {len(X)} feature vectors")

    feature_names = list(X[0].keys())

    # 时间切分：2025年之前训练，2025年及之后测试
    split_date = '2025-01-01'
    X_train, y_train = [], []
    X_test, y_test = [], []

    for features, label, date in zip(X, y, dates):
        if date < split_date:
            X_train.append(features)
            y_train.append(label)
        else:
            X_test.append(features)
            y_test.append(label)

    print(f"\nTrain (before {split_date}): {len(X_train)}")
    print(f"Test ({split_date}+): {len(X_test)}")

    # 转成列表（保留 league 字符串）
    league_idx_cls = feature_names.index('league') if 'league' in feature_names else None
    cat_features_cls = [league_idx_cls] if league_idx_cls is not None else []

    def to_rows_cls(feat_list):
        return [[f.get(k, 0.0) if k != 'league' else f.get(k, 'unknown') for k in feature_names] for f in feat_list]

    X_train_arr = to_rows_cls(X_train)
    y_train_arr = np.array(y_train)
    X_test_arr = to_rows_cls(X_test)
    y_test_arr = np.array(y_test)

    # 训练 CatBoost
    print("\nTraining CatBoost...")
    from catboost import CatBoostClassifier, Pool

    train_pool = Pool(X_train_arr, y_train_arr, cat_features=cat_features_cls)
    test_pool = Pool(X_test_arr, y_test_arr, cat_features=cat_features_cls)

    # class_weights: 平局(1)在实际数据中占比~23%，主胜(0)~50%，客胜(2)~28%
    # 用反比权重让模型更重视少数类（平局）
    model = CatBoostClassifier(
        iterations=1000,
        learning_rate=0.05,
        depth=6,
        loss_function='MultiClass',
        eval_metric='MultiClass',
        early_stopping_rounds=50,
        verbose=100,
        task_type='CPU',
        class_weights=[1.0, 2.2, 1.8],  # 0=主胜, 1=平局, 2=客胜
    )

    model.fit(train_pool, eval_set=test_pool)

    # 评估
    train_acc = model.score(train_pool)
    test_acc = model.score(test_pool)

    print(f"\nTrain accuracy: {train_acc:.2%}")
    print(f"Test accuracy: {test_acc:.2%}")

    # 计算 RPS
    def rps(probs, actual):
        cum_probs = np.cumsum(probs)
        cum_actual = np.cumsum([1 if actual == i else 0 for i in range(3)])
        return np.mean((cum_probs - cum_actual) ** 2)

    preds = model.predict_proba(test_pool)
    rps_scores = [rps(p, a) for p, a in zip(preds, y_test_arr)]
    avg_rps = np.mean(rps_scores)

    print(f"\nTest RPS: {avg_rps:.4f}")
    print(f"Random guess RPS: 0.3333")
    print(f"Odds-only baseline RPS: ~0.195")

    # 特征重要性
    print("\nTop 10 feature importances:")
    importances = model.get_feature_importance()
    for name, imp in sorted(zip(feature_names, importances), key=lambda x: -x[1])[:10]:
        print(f"  {name}: {imp:.2f}")

    # 保存分类模型
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, "catboost_v1.cbm")
    model.save_model(model_path)

    with open(os.path.join(MODEL_DIR, "features_v1.json"), "w") as f:
        json.dump(feature_names, f)

    # 保存 Pi-Ratings
    pi_serializable = {k: v for k, v in pi_ratings.items()}
    with open(os.path.join(MODEL_DIR, "pi_ratings_v1.json"), "w") as f:
        json.dump(pi_serializable, f)

    # 保存联赛统计
    league_stats_serializable = {k: {kk: float(vv) for kk, vv in v.items()} for k, v in league_stats.items()}
    with open(os.path.join(MODEL_DIR, "league_stats_v1.json"), "w") as f:
        json.dump(league_stats_serializable, f)

    print(f"\nClassification model saved to {model_path}")
    print(f"Pi-Ratings saved ({len(pi_ratings)} teams)")
    print(f"Feature names saved")

    # ========== 训练泊松回归模型（预测进球数） ==========
    print("\n" + "=" * 50)
    print("Training Poisson Regression Models for Score Prediction")
    print("=" * 50)

    # 重新构建数据，这次包含进球数
    X_goals_train = []
    X_goals_test = []
    y_home_train = []
    y_away_train = []
    y_home_test = []
    y_away_test = []

    for match in matches:
        features = build_features(match, pi_ratings, team_index, h2h_index, league_stats)

        if features is None:
            continue

        home_goals = float(match['home_goals'])
        away_goals = float(match['away_goals'])

        if str(match['date'])[:10] < split_date:
            X_goals_train.append(features)
            y_home_train.append(home_goals)
            y_away_train.append(away_goals)
        else:
            X_goals_test.append(features)
            y_home_test.append(home_goals)
            y_away_test.append(away_goals)

    print(f"\nGoals prediction - Train: {len(X_goals_train)}, Test: {len(X_goals_test)}")

    # league 是 categorical 特征
    league_idx = feature_names.index('league') if 'league' in feature_names else None
    cat_features = [league_idx] if league_idx is not None else []

    # 转成列表（保留字符串类型）
    def to_rows(feat_list):
        return [[f.get(k, 0.0) if k != 'league' else f.get(k, 'unknown') for k in feature_names] for f in feat_list]

    X_goals_train_arr = to_rows(X_goals_train)
    X_goals_test_arr = to_rows(X_goals_test)
    y_home_train_arr = np.array(y_home_train)
    y_away_train_arr = np.array(y_away_train)
    y_home_test_arr = np.array(y_home_test)
    y_away_test_arr = np.array(y_away_test)

    # 训练主队进球模型
    from catboost import CatBoostRegressor

    print("\n=== Training Home Goals Model ===")
    home_goals_pool_train = Pool(X_goals_train_arr, y_home_train_arr, cat_features=cat_features)
    home_goals_pool_test = Pool(X_goals_test_arr, y_home_test_arr, cat_features=cat_features)

    home_model = CatBoostRegressor(
        iterations=1000,
        learning_rate=0.05,
        depth=6,
        loss_function='Poisson',
        eval_metric='RMSE',
        early_stopping_rounds=50,
        verbose=100,
        task_type='CPU',
    )
    home_model.fit(home_goals_pool_train, eval_set=home_goals_pool_test)

    home_train_rmse = np.sqrt(np.mean((home_model.predict(home_goals_pool_train) - y_home_train_arr) ** 2))
    home_test_rmse = np.sqrt(np.mean((home_model.predict(home_goals_pool_test) - y_home_test_arr) ** 2))
    print(f"Home Goals - Train RMSE: {home_train_rmse:.4f}, Test RMSE: {home_test_rmse:.4f}")

    # 训练客队进球模型
    print("\n=== Training Away Goals Model ===")
    away_goals_pool_train = Pool(X_goals_train_arr, y_away_train_arr, cat_features=cat_features)
    away_goals_pool_test = Pool(X_goals_test_arr, y_away_test_arr, cat_features=cat_features)

    away_model = CatBoostRegressor(
        iterations=1000,
        learning_rate=0.05,
        depth=6,
        loss_function='Poisson',
        eval_metric='RMSE',
        early_stopping_rounds=50,
        verbose=100,
        task_type='CPU',
    )
    away_model.fit(away_goals_pool_train, eval_set=away_goals_pool_test)

    away_train_rmse = np.sqrt(np.mean((away_model.predict(away_goals_pool_train) - y_away_train_arr) ** 2))
    away_test_rmse = np.sqrt(np.mean((away_model.predict(away_goals_pool_test) - y_away_test_arr) ** 2))
    print(f"Away Goals - Train RMSE: {away_train_rmse:.4f}, Test RMSE: {away_test_rmse:.4f}")

    # 保存进球预测模型
    home_model_path = os.path.join(MODEL_DIR, "home_goals_v1.cbm")
    away_model_path = os.path.join(MODEL_DIR, "away_goals_v1.cbm")
    home_model.save_model(home_model_path)
    away_model.save_model(away_model_path)

    print(f"\nHome goals model saved to {home_model_path}")
    print(f"Away goals model saved to {away_model_path}")

    await db.disconnect()

    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
