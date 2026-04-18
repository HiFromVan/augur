"""
阈值决策搜索：用 DB 里已有的混合预测概率，测试不同 threshold_draw 对准确率的影响。
核心思路：不用 argmax，改成 "draw_prob > threshold → 预测平局"
"""
import asyncio, asyncpg

DATABASE_URL = "postgresql://postgres:HpIDTBRIXSvZTaCGdlCvjJVZUgGuESNg@mainline.proxy.rlwy.net:52425/railway"


def decide(pred_home, pred_draw, pred_away, threshold_draw):
    if pred_draw > threshold_draw:
        return "draw"
    return "home" if pred_home > pred_away else "away"


async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    records = [dict(r) for r in await conn.fetch("""
        SELECT pr.pred_home, pr.pred_draw, pr.pred_away,
               pr.actual_home, pr.actual_away
        FROM prediction_records pr
        WHERE pr.actual_home IS NOT NULL
        ORDER BY pr.id
    """)]
    await conn.close()

    total = len(records)
    print(f"共 {total} 条历史预测记录\n")

    # 实际结果分布
    actuals = []
    for r in records:
        if r["actual_home"] > r["actual_away"]:
            actuals.append("home")
        elif r["actual_home"] == r["actual_away"]:
            actuals.append("draw")
        else:
            actuals.append("away")

    from collections import Counter
    dist = Counter(actuals)
    print(f"实际结果分布: 主胜={dist['home']} 平局={dist['draw']} 客胜={dist['away']}")
    print(f"平局率: {dist['draw']/total*100:.1f}%\n")

    print(f"{'threshold':>10} {'acc%':>7} {'draw_preds':>11} {'draw_hit':>9} {'draw_recall%':>13}")
    print("-" * 55)

    best = {"acc": 0, "threshold": 0}
    for t in [round(x * 0.01, 2) for x in range(22, 40)]:
        correct = draw_preds = draw_hit = draw_actual = 0
        for r, actual in zip(records, actuals):
            pred = decide(r["pred_home"], r["pred_draw"], r["pred_away"], t)
            if pred == actual:
                correct += 1
            if pred == "draw":
                draw_preds += 1
            if pred == "draw" and actual == "draw":
                draw_hit += 1
            if actual == "draw":
                draw_actual += 1

        acc = correct / total * 100
        recall = draw_hit / draw_actual * 100 if draw_actual else 0
        print(f"{t:>10.2f} {acc:>7.1f}% {draw_preds:>11} {draw_hit:>9} {recall:>12.1f}%")
        if acc > best["acc"] and draw_preds >= 3:
            best = {"acc": acc, "threshold": t, "draw_preds": draw_preds,
                    "draw_hit": draw_hit, "recall": recall}

    print(f"\n最优阈值: threshold_draw={best['threshold']}")
    print(f"准确率: {best['acc']:.1f}%, 平局预测: {best['draw_preds']} 场, 命中: {best['draw_hit']}, 平局召回率: {best['recall']:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
