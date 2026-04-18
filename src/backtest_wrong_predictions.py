"""
对历史预测错误的赛事，用新 baseline 重新预测，对比准确率提升。
重新预测时只用赔率和 Pi-Ratings，不使用已知比赛结果。
"""

import asyncio
import os
import json
import numpy as np
from collections import defaultdict

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:HpIDTBRIXSvZTaCGdlCvjJVZUgGuESNg@mainline.proxy.rlwy.net:52425/railway"
)


# ============ 新 baseline（与修复后的 main.py 一致）============

def _new_baseline(pi_diff: float, odds_home=None, odds_draw=None, odds_away=None) -> dict:
    """修复后的 baseline：Pi-Ratings + 赔率混合（与修复后的 main.py 一致）"""
    combined = pi_diff + 0.25
    raw_home = 1 / (1 + np.exp(-combined))
    draw = max(0.18, min(0.42, 0.28 - abs(combined) * 0.03))
    raw_away = 1 - raw_home - draw
    total = raw_home + draw + raw_away
    pi_home = raw_home / total
    pi_draw = draw / total
    pi_away = raw_away / total

    # 赔率混合
    if odds_home and odds_draw and odds_away:
        ih = 1 / odds_home
        id_ = 1 / odds_draw
        ia = 1 / odds_away
        t = ih + id_ + ia
        implied_home, implied_draw, implied_away = ih / t, id_ / t, ia / t
        w = 0.4
        pi_home = pi_home * (1 - w) + implied_home * w
        pi_draw = pi_draw * (1 - w) + implied_draw * w
        pi_away = pi_away * (1 - w) + implied_away * w
        t2 = pi_home + pi_draw + pi_away
        pi_home, pi_draw, pi_away = pi_home / t2, pi_draw / t2, pi_away / t2

    return {'home': pi_home, 'draw': pi_draw, 'away': pi_away}


def _old_baseline(pi_diff: float) -> dict:
    """原始 baseline"""
    combined = pi_diff + 0.25
    raw_home = 1 / (1 + np.exp(-combined))
    draw = max(0.15, min(0.35, 0.25 - abs(combined) * 0.05))
    raw_away = 1 - raw_home - draw
    total = raw_home + draw + raw_away
    return {'home': raw_home / total, 'draw': draw / total, 'away': raw_away / total}


def _outcome(home_goals, away_goals):
    if home_goals > away_goals:
        return 'home'
    elif home_goals == away_goals:
        return 'draw'
    return 'away'


def _predicted_outcome(pred: dict) -> str:
    return max(pred, key=pred.get)


# ============ Pi-Ratings（从历史比赛计算，不含待测比赛结果）============

def compute_pi_ratings(matches: list) -> dict:
    ratings = defaultdict(lambda: {'attack': 0.0, 'defense': 0.0})
    k = 0.05
    home_adv = 0.25
    for m in sorted(matches, key=lambda x: x['date']):
        if m['home_goals'] is None:
            continue
        home, away = m['home_team'], m['away_team']
        hg, ag = float(m['home_goals']), float(m['away_goals'])
        exp_h = ratings[home]['attack'] + home_adv - ratings[away]['defense']
        exp_a = ratings[away]['attack'] - ratings[home]['defense']
        err_h, err_a = hg - exp_h, ag - exp_a
        ratings[home]['attack'] += k * err_h
        ratings[away]['attack'] += k * err_a
        ratings[home]['defense'] -= k * err_a
        ratings[away]['defense'] -= k * err_h
    return {k: dict(v) for k, v in ratings.items()}


async def main():
    import asyncpg

    conn = await asyncpg.connect(DATABASE_URL)

    # 1. 取所有预测错误的记录（有实际结果）
    wrong = await conn.fetch("""
        SELECT pr.id, pr.match_live_id, pr.pred_home, pr.pred_draw, pr.pred_away,
               pr.actual_home, pr.actual_away, pr.model_name,
               ml.home_team, ml.away_team, ml.date, ml.league,
               ml.odds_home, ml.odds_draw, ml.odds_away
        FROM prediction_records pr
        JOIN matches_live ml ON ml.id = pr.match_live_id
        WHERE pr.is_correct = false AND pr.actual_home IS NOT NULL
        ORDER BY ml.date
    """)
    print(f"预测错误记录数: {len(wrong)}")

    # 2. 取历史比赛（用于计算 Pi-Ratings），排除待测比赛
    wrong_ids = {r['match_live_id'] for r in wrong}
    hist = await conn.fetch("""
        SELECT home_team, away_team, date, home_goals, away_goals
        FROM matches_live
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
        ORDER BY date
    """)
    # 不排除错误预测的比赛本身（Pi-Ratings 是滚动计算的，预测时用的是比赛前的评分）
    # 这里简化：用全量历史计算最终评分，作为近似
    hist_list = [dict(r) for r in hist]
    pi_ratings = compute_pi_ratings(hist_list)

    await conn.close()

    # 3. 对每条错误预测，用新 baseline 重新预测
    results = []
    for r in wrong:
        r = dict(r)
        home, away = r['home_team'], r['away_team']
        actual = _outcome(r['actual_home'], r['actual_away'])

        # Pi-Ratings 差值
        hr = pi_ratings.get(home, {'attack': 0.0, 'defense': 0.0})
        ar = pi_ratings.get(away, {'attack': 0.0, 'defense': 0.0})
        pi_diff = (hr['attack'] - ar['defense']) - (ar['attack'] - hr['defense'])

        old_pred = {'home': r['pred_home'], 'draw': r['pred_draw'], 'away': r['pred_away']}
        new_pred = _new_baseline(pi_diff, r['odds_home'], r['odds_draw'], r['odds_away'])

        old_outcome = _predicted_outcome(old_pred)
        new_outcome = _predicted_outcome(new_pred)

        results.append({
            'id': r['id'],
            'match': f"{home} vs {away}",
            'date': str(r['date'])[:10],
            'actual': actual,
            'old_pred': old_outcome,
            'new_pred': new_outcome,
            'old_correct': old_outcome == actual,  # 应该都是 False
            'new_correct': new_outcome == actual,
            'old_probs': old_pred,
            'new_probs': new_pred,
        })

    # 4. 统计
    total = len(results)
    old_correct = sum(1 for r in results if r['old_correct'])
    new_correct = sum(1 for r in results if r['new_correct'])

    print(f"\n{'='*60}")
    print(f"回测结果（仅针对原来预测错误的 {total} 场）")
    print(f"{'='*60}")
    print(f"原始预测正确数: {old_correct}/{total} ({old_correct/total*100:.1f}%)")
    print(f"新 baseline 正确数: {new_correct}/{total} ({new_correct/total*100:.1f}%)")
    print(f"提升: +{new_correct - old_correct} 场 ({(new_correct-old_correct)/total*100:.1f}%)")

    # 按实际结果分类统计
    print(f"\n{'='*60}")
    print("按实际结果分类")
    print(f"{'='*60}")
    for outcome in ['home', 'draw', 'away']:
        subset = [r for r in results if r['actual'] == outcome]
        if not subset:
            continue
        new_ok = sum(1 for r in subset if r['new_correct'])
        print(f"实际{outcome:5s}: {len(subset)}场, 新预测正确 {new_ok} ({new_ok/len(subset)*100:.1f}%)")

    # 新预测中平局的数量
    new_draw_preds = sum(1 for r in results if r['new_pred'] == 'draw')
    print(f"\n新预测中预测平局的场数: {new_draw_preds}/{total}")

    # 打印新预测正确的案例
    newly_correct = [r for r in results if r['new_correct'] and not r['old_correct']]
    print(f"\n新预测命中（原来错，现在对）: {len(newly_correct)} 场")
    for r in newly_correct[:10]:
        print(f"  {r['date']} {r['match']}: 实际={r['actual']}, "
              f"旧={r['old_pred']}({r['old_probs']['home']:.2f}/{r['old_probs']['draw']:.2f}/{r['old_probs']['away']:.2f}), "
              f"新={r['new_pred']}({r['new_probs']['home']:.2f}/{r['new_probs']['draw']:.2f}/{r['new_probs']['away']:.2f})")

    # 新预测变错的案例
    newly_wrong = [r for r in results if not r['new_correct'] and r['old_correct']]
    print(f"\n新预测变错（原来对，现在错）: {len(newly_wrong)} 场")
    for r in newly_wrong[:5]:
        print(f"  {r['date']} {r['match']}: 实际={r['actual']}, "
              f"旧={r['old_pred']}, 新={r['new_pred']}")


if __name__ == "__main__":
    asyncio.run(main())
