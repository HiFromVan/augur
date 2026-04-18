"""
双模型联合预测测试：
- draw_classifier 判断是否平局
- 主模型判断主胜/客胜
找最优 draw_threshold
"""
import asyncio, asyncpg, json, numpy as np, math
from collections import defaultdict
from catboost import CatBoostClassifier

DATABASE_URL = "postgresql://postgres:HpIDTBRIXSvZTaCGdlCvjJVZUgGuESNg@mainline.proxy.rlwy.net:52425/railway"

main_model = CatBoostClassifier()
main_model.load_model("models/catboost_v1.cbm")
draw_model = CatBoostClassifier()
draw_model.load_model("models/draw_classifier_v1.cbm")

with open("models/features_v1.json") as f:
    feature_names = json.load(f)
with open("models/pi_ratings_v1.json") as f:
    pi_ratings_global = json.load(f)
with open("models/league_stats_v1.json") as f:
    league_stats = json.load(f)


def compute_pi_before(all_matches, target_id):
    ratings = defaultdict(lambda: {"attack": 0.0, "defense": 0.0})
    k, adv = 0.05, 0.25
    for m in sorted(all_matches, key=lambda x: x["date"]):
        if m["id"] == target_id:
            break
        if m["home_goals"] is None:
            continue
        h, a = m["home_team"], m["away_team"]
        hg, ag = float(m["home_goals"]), float(m["away_goals"])
        exp_h = ratings[h]["attack"] + adv - ratings[a]["defense"]
        exp_a = ratings[a]["attack"] - ratings[h]["defense"]
        err_h, err_a = hg - exp_h, ag - exp_a
        ratings[h]["attack"] += k * err_h; ratings[a]["attack"] += k * err_a
        ratings[h]["defense"] -= k * err_a; ratings[a]["defense"] -= k * err_h
    return {k: dict(v) for k, v in ratings.items()}


def recent_form(team, all_matches, match_date, n=5):
    ms = sorted([m for m in all_matches if (m["home_team"] == team or m["away_team"] == team)
                 and m["home_goals"] is not None and m["date"] < match_date], key=lambda x: x["date"])[-n:]
    if not ms: return 0.33, 1.0, 1.0, 1.0
    wins = draws = gs = gc = 0
    for m in ms:
        ih = m["home_team"] == team
        tg = m["home_goals"] if ih else m["away_goals"]
        og = m["away_goals"] if ih else m["home_goals"]
        gs += tg; gc += og
        if tg > og: wins += 1
        elif tg == og: draws += 1
    t = len(ms)
    return wins/t, gs/t, gc/t, (wins*3+draws)/t


def draw_rate_fn(team, all_matches, match_date, side, n=5):
    ms = sorted([m for m in all_matches if m[f"{side}_team"] == team and m["home_goals"] is not None
                 and m["date"] < match_date], key=lambda x: x["date"])[-n:]
    if not ms: return 0.25
    return sum(1 for m in ms if m["home_goals"] == m["away_goals"]) / len(ms)


def h2h(home, away, all_matches, match_date, n=10):
    ms = sorted([m for m in all_matches if {m["home_team"], m["away_team"]} == {home, away}
                 and m["home_goals"] is not None and m["date"] < match_date], key=lambda x: x["date"])[-n:]
    if not ms: return 0.33, 0.0, 2.5
    hw = sum(1 for m in ms if m["home_goals"] > m["away_goals"])
    dr = sum(1 for m in ms if m["home_goals"] == m["away_goals"])
    gl = sum(m["home_goals"] + m["away_goals"] for m in ms) / len(ms)
    return (hw + dr*0.5)/len(ms), dr/len(ms), gl


def smart_blend(pred, features, mw=0.55, db=1.20):
    ih = features.get("implied_home", 0)
    id_ = features.get("implied_draw", 0)
    ia = features.get("implied_away", 0)
    if ih + id_ + ia < 0.5:
        return pred
    pi_sum = abs(features.get("pi_attack_home", 0)) + abs(features.get("pi_defense_home", 0)) + \
             abs(features.get("pi_attack_away", 0)) + abs(features.get("pi_defense_away", 0))
    model_weight = 0.0 if pi_sum < 0.5 else (0.3 if pi_sum < 2.0 else mw)
    w = 1 - model_weight
    ph = pred["home"] * model_weight + ih * w
    pd = pred["draw"] * model_weight + id_ * w
    pa = pred["away"] * model_weight + ia * w
    pd *= db
    t = ph + pd + pa
    return {"home": ph/t, "draw": pd/t, "away": pa/t}


async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    all_ml = [dict(r) for r in await conn.fetch(
        "SELECT id, home_team, away_team, date, home_goals, away_goals FROM matches_live WHERE home_goals IS NOT NULL ORDER BY date"
    )]
    records = [dict(r) for r in await conn.fetch("""
        SELECT pr.id, pr.match_live_id, pr.actual_home, pr.actual_away,
               ml.home_team, ml.away_team, ml.date, ml.league,
               ml.odds_home, ml.odds_draw, ml.odds_away
        FROM prediction_records pr
        JOIN matches_live ml ON ml.id = pr.match_live_id
        WHERE pr.actual_home IS NOT NULL ORDER BY ml.date
    """)]
    await conn.close()

    print(f"预计算 {len(records)} 场特征...")
    precomputed = []
    for r in records:
        pi = compute_pi_before(all_ml, r["match_live_id"])
        home, away = r["home_team"], r["away_team"]
        hr = pi.get(home, pi_ratings_global.get(home, {"attack": 0.0, "defense": 0.0}))
        ar = pi.get(away, pi_ratings_global.get(away, {"attack": 0.0, "defense": 0.0}))
        pi_diff = (hr["attack"] - ar["defense"]) - (ar["attack"] - hr["defense"])
        match_date = r["date"]
        hw, hs, hc, hp = recent_form(home, all_ml, match_date)
        aw, as_, ac, ap = recent_form(away, all_ml, match_date)
        h2h_rate, h2h_dr, h2h_gl = h2h(home, away, all_ml, match_date)
        adr = draw_rate_fn(away, all_ml, match_date, "away")
        hdr = draw_rate_fn(home, all_ml, match_date, "home")
        league = r["league"]
        ls = league_stats.get(league) or league_stats.get("__global__") or {}
        oh = r["odds_home"] or 0.0; od = r["odds_draw"] or 0.0; oa = r["odds_away"] or 0.0
        impl_h = impl_d = impl_a = 1/3
        odds_entropy = 1.0
        if oh and od and oa:
            ih, id_, ia = 1/oh, 1/od, 1/oa
            t = ih + id_ + ia
            impl_h, impl_d, impl_a = ih/t, id_/t, ia/t
            odds_entropy = -sum(p * math.log(p) for p in [impl_h, impl_d, impl_a] if p > 0) / math.log(3)
        strength_parity = max(0.0, 1.0 - abs(pi_diff) / 2.0)
        feat = {
            "pi_attack_home": hr["attack"], "pi_defense_home": hr["defense"],
            "pi_attack_away": ar["attack"], "pi_defense_away": ar["defense"],
            "pi_diff": pi_diff, "home_advantage": 0.25, "league": league,
            "win_rate_home_5": hw, "goals_scored_home_5": hs, "goals_conceded_home_5": hc, "points_home_5": hp,
            "win_rate_away_5": aw, "goals_scored_away_5": as_, "goals_conceded_away_5": ac, "points_away_5": ap,
            "h2h_win_rate": h2h_rate, "h2h_draw_rate": h2h_dr, "h2h_avg_goals": h2h_gl,
            "implied_home": impl_h, "implied_draw": impl_d, "implied_away": impl_a,
            "odds_home": oh, "odds_draw": od, "odds_away": oa,
            "asian_home": 0.0, "asian_away": 0.0, "ou_line": 0.0, "ou_over": 0.0, "ou_under": 0.0,
            "league_avg_home_goals": ls.get("avg_home", 1.36),
            "league_avg_away_goals": ls.get("avg_away", 1.18),
            "league_avg_total_goals": ls.get("avg_total", 2.54),
            "league_draw_rate": ls.get("draw_rate", 0.25),
            "away_draw_rate_5": adr, "home_draw_rate_5": hdr,
            "strength_parity": strength_parity, "odds_entropy": odds_entropy,
        }
        vec = [feat.get(k, 0.0) if k != "league" else feat.get(k, "unknown") for k in feature_names]
        main_probs = main_model.predict_proba([vec])[0]
        draw_prob = draw_model.predict_proba([vec])[0][1]
        raw_pred = {"home": float(main_probs[0]), "draw": float(main_probs[1]), "away": float(main_probs[2])}
        actual = "home" if r["actual_home"] > r["actual_away"] else ("draw" if r["actual_home"] == r["actual_away"] else "away")
        precomputed.append({"raw_pred": raw_pred, "feat": feat, "actual": actual, "draw_prob": draw_prob})

    print(f"预计算完成\n")

    # 分析 draw_classifier 的区分能力
    dp_draw = [p["draw_prob"] for p in precomputed if p["actual"] == "draw"]
    dp_other = [p["draw_prob"] for p in precomputed if p["actual"] != "draw"]
    print(f"draw_classifier 平局概率分布:")
    print(f"  实际平局 ({len(dp_draw)}场): avg={np.mean(dp_draw):.3f}, median={np.median(dp_draw):.3f}, max={max(dp_draw):.3f}")
    print(f"  实际非平局 ({len(dp_other)}场): avg={np.mean(dp_other):.3f}, median={np.median(dp_other):.3f}, max={max(dp_other):.3f}")
    print(f"  区分度: {np.mean(dp_draw) - np.mean(dp_other):.3f}\n")

    # 搜索最优阈值（双模型策略）
    print(f"{'thr':>6} {'acc%':>7} {'draws':>7} {'draw_hit':>9} {'recall%':>9}")
    print("-" * 45)

    best = {"acc": 0}
    draw_actual = sum(1 for p in precomputed if p["actual"] == "draw")

    for thr in [round(x * 0.01, 2) for x in range(30, 75)]:
        correct = draw_preds = draw_hit = 0
        for p in precomputed:
            if p["draw_prob"] > thr:
                predicted = "draw"
            else:
                blended = smart_blend(p["raw_pred"], p["feat"])
                predicted = "home" if blended["home"] > blended["away"] else "away"
            if predicted == p["actual"]: correct += 1
            if predicted == "draw": draw_preds += 1
            if predicted == "draw" and p["actual"] == "draw": draw_hit += 1
        acc = correct / len(precomputed) * 100
        recall = draw_hit / draw_actual * 100 if draw_actual else 0
        print(f"{thr:>6.2f} {acc:>7.1f}% {draw_preds:>7} {draw_hit:>9} {recall:>8.1f}%")
        if acc > best.get("acc", 0) and draw_preds >= 3:
            best = {"acc": acc, "thr": thr, "draw_preds": draw_preds, "draw_hit": draw_hit, "recall": recall}

    print(f"\n最优阈值: draw_threshold={best['thr']}")
    print(f"准确率: {best['acc']:.1f}%, 平局预测: {best['draw_preds']} 场, 命中: {best['draw_hit']}, 召回率: {best['recall']:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
