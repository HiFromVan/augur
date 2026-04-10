#!/usr/bin/env python3
"""
定时任务：为未来比赛生成AI分析
- AI预测说明（ai_explanation）
- 媒体分析（media_analysis）
"""

import asyncio
import asyncpg
import os
import json
import sys
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入配置
from config import ENABLE_AI_FEATURES, DB_CONFIG

# 检查AI功能是否启用
if not ENABLE_AI_FEATURES:
    print("AI功能已关闭 (config.py: ENABLE_AI_FEATURES = False)")
    print("如需启用，请修改 config.py 中的 ENABLE_AI_FEATURES = True")
    sys.exit(0)

# AI功能启用时才导入anthropic
import anthropic

# Anthropic API配置
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

anthropic_client = anthropic.Anthropic(
    api_key=ANTHROPIC_API_KEY,
    base_url=ANTHROPIC_BASE_URL,
)


async def generate_ai_explanation(match_data: dict, pred: dict, features: dict) -> str:
    """生成AI预测说明"""
    try:
        home_team = match_data.get("home_team_cn") or match_data.get("home_team")
        away_team = match_data.get("away_team_cn") or match_data.get("away_team")

        prompt = f"""你是一位专业的足球数据分析师。请基于以下数据，用简洁的中文（80-120字）解释这场比赛的预测结果：

比赛：{home_team} vs {away_team}
预测概率：主胜 {pred['pred_home']:.1%} | 平局 {pred['pred_draw']:.1%} | 客胜 {pred['pred_away']:.1%}

关键数据：
- 主队进攻评分：{features.get('pi_attack_home', 0):.1f}，防守评分：{features.get('pi_defense_home', 0):.1f}
- 客队进攻评分：{features.get('pi_attack_away', 0):.1f}，防守评分：{features.get('pi_defense_away', 0):.1f}
- 主队近5场胜率：{features.get('win_rate_home_5', 0):.1%}，场均进球：{features.get('goals_scored_home_5', 0):.1f}
- 客队近5场胜率：{features.get('win_rate_away_5', 0):.1%}，场均进球：{features.get('goals_scored_away_5', 0):.1f}

要求：
1. 直接说明预测结果和主要原因
2. 突出最关键的1-2个数据指标
3. 语言简洁专业，不要废话
4. 80-120字"""

        response = anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}]
        )

        explanation = response.content[0].text.strip()
        print(f"  ✓ AI说明已生成: {explanation[:50]}...")
        return explanation

    except Exception as e:
        print(f"  ✗ AI说明生成失败: {e}")
        return None


async def generate_media_analysis(match_data: dict, pred: dict, home_pi: dict, away_pi: dict,
                                  h2h_list: list, home_form: list, away_form: list) -> dict:
    """生成媒体分析 - 基于网络搜索的真实新闻"""
    try:
        home_team = match_data.get("home_team_cn") or match_data.get("home_team")
        away_team = match_data.get("away_team_cn") or match_data.get("away_team")

        print(f"  搜索新闻: {home_team} vs {away_team}...")

        # Stage 1: 搜索真实新闻
        search_prompt = f"""请搜索并总结以下两支足球队最近的新闻、伤病情况、阵容变化等信息：

主队：{home_team}
客队：{away_team}

请重点关注：
1. 最近一周的比赛结果和表现
2. 关键球员的伤病情况
3. 主教练的战术调整
4. 球队士气和更衣室动态
5. 任何可能影响即将到来比赛的因素

请用简洁的中文总结（150字以内）。"""

        search_response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=512,
            messages=[{"role": "user", "content": search_prompt}]
        )

        news_context = search_response.content[0].text.strip()
        print(f"  ✓ 新闻搜索完成: {news_context[:50]}...")

        # Stage 2: 基于新闻生成分析
        h2h_summary = f"历史交锋 {len(h2h_list)} 场" if h2h_list else "无历史交锋"
        home_form_str = "".join(["胜" if f.get("result") == "W" else "平" if f.get("result") == "D" else "负" for f in (home_form or [])[:5]])
        away_form_str = "".join(["胜" if f.get("result") == "W" else "平" if f.get("result") == "D" else "负" for f in (away_form or [])[:5]])

        media_prompt = f"""你是一位专业的足球赛事分析师。请基于以下信息生成一份赛前媒体分析（250-350字）：

【最新媒体动态】
{news_context}

【数据分析】
比赛：{home_team} vs {away_team}
预测：主胜 {pred['pred_home']:.1%} | 平局 {pred['pred_draw']:.1%} | 客胜 {pred['pred_away']:.1%}

实力对比：
- 主队：进攻 {home_pi.get('attack', 0):.1f} | 防守 {home_pi.get('defense', 0):.1f}
- 客队：进攻 {away_pi.get('attack', 0):.1f} | 防守 {away_pi.get('defense', 0):.1f}

近期状态：
- {home_team}：{home_form_str or '暂无'}
- {away_team}：{away_form_str or '暂无'}

{h2h_summary}

要求：
1. 优先使用最新媒体动态信息
2. 结合数据分析提供专业见解
3. 分析双方优劣势和关键对抗点
4. 使用专业足球媒体的语言风格
5. 250-350字，分2-3段"""

        media_response = anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": media_prompt}]
        )

        summary = media_response.content[0].text.strip()
        print(f"  ✓ 媒体分析已生成: {summary[:50]}...")

        return {
            "summary": summary,
            "generated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"  ✗ 媒体分析生成失败: {e}")
        return None


async def process_match(conn, match_id: int):
    """处理单场比赛的AI分析生成"""
    print(f"\n处理比赛 {match_id}...")

    # 获取比赛数据
    match = await conn.fetchrow("""
        SELECT m.*, p.pred_home_win, p.pred_draw, p.pred_away_win,
               p.expected_goals_home, p.expected_goals_away,
               p.ai_explanation
        FROM matches_live m
        LEFT JOIN predictions p ON m.id = p.match_id
        WHERE m.id = $1
    """, match_id)

    if not match:
        print(f"  ✗ 比赛不存在")
        return

    match_data = dict(match)

    # 检查是否已有AI说明
    has_explanation = match_data.get("ai_explanation") is not None

    # 检查是否已有媒体分析
    media_analysis = await conn.fetchrow("""
        SELECT summary, generated_at
        FROM media_analysis
        WHERE match_id = $1
    """, match_id)
    has_media = media_analysis is not None

    if has_explanation and has_media:
        print(f"  ⊙ 已有完整分析，跳过")
        return

    # 获取特征数据
    features = await conn.fetchrow("""
        SELECT * FROM match_features WHERE match_id = $1
    """, match_id)

    if not features:
        print(f"  ✗ 缺少特征数据")
        return

    features_dict = dict(features)

    # 获取Pi-Ratings
    home_pi = await conn.fetchrow("""
        SELECT attack, defense FROM pi_ratings
        WHERE team = $1 AND date <= $2
        ORDER BY date DESC LIMIT 1
    """, match_data["home_team"], match_data["date"])

    away_pi = await conn.fetchrow("""
        SELECT attack, defense FROM pi_ratings
        WHERE team = $1 AND date <= $2
        ORDER BY date DESC LIMIT 1
    """, match_data["away_team"], match_data["date"])

    home_pi_dict = dict(home_pi) if home_pi else {"attack": 0, "defense": 0}
    away_pi_dict = dict(away_pi) if away_pi else {"attack": 0, "defense": 0}

    # 获取历史交锋
    h2h_list = await conn.fetch("""
        SELECT date, home_team, away_team, home_goals, away_goals
        FROM matches_history
        WHERE ((home_team = $1 AND away_team = $2) OR (home_team = $2 AND away_team = $1))
          AND date < $3
          AND home_goals IS NOT NULL
        ORDER BY date DESC LIMIT 5
    """, match_data["home_team"], match_data["away_team"], match_data["date"])

    # 获取近期战绩
    home_form = await conn.fetch("""
        SELECT date,
               CASE WHEN home_team = $1 THEN away_team ELSE home_team END as opponent,
               CASE WHEN home_team = $1 THEN home_goals ELSE away_goals END as goals_for,
               CASE WHEN home_team = $1 THEN away_goals ELSE home_goals END as goals_against,
               CASE
                   WHEN home_team = $1 AND home_goals > away_goals THEN 'W'
                   WHEN away_team = $1 AND away_goals > home_goals THEN 'W'
                   WHEN home_goals = away_goals THEN 'D'
                   ELSE 'L'
               END as result,
               home_team = $1 as is_home
        FROM matches_history
        WHERE (home_team = $1 OR away_team = $1)
          AND date < $2
          AND home_goals IS NOT NULL
        ORDER BY date DESC LIMIT 5
    """, match_data["home_team"], match_data["date"])

    away_form = await conn.fetch("""
        SELECT date,
               CASE WHEN home_team = $1 THEN away_team ELSE home_team END as opponent,
               CASE WHEN home_team = $1 THEN home_goals ELSE away_goals END as goals_for,
               CASE WHEN home_team = $1 THEN away_goals ELSE home_goals END as goals_against,
               CASE
                   WHEN home_team = $1 AND home_goals > away_goals THEN 'W'
                   WHEN away_team = $1 AND away_goals > home_goals THEN 'W'
                   WHEN home_goals = away_goals THEN 'D'
                   ELSE 'L'
               END as result,
               home_team = $1 as is_home
        FROM matches_history
        WHERE (home_team = $1 OR away_team = $1)
          AND date < $2
          AND home_goals IS NOT NULL
        ORDER BY date DESC LIMIT 5
    """, match_data["away_team"], match_data["date"])

    pred = {
        "pred_home": match_data.get("pred_home_win") or 0,
        "pred_draw": match_data.get("pred_draw") or 0,
        "pred_away": match_data.get("pred_away_win") or 0,
    }

    # 生成AI说明（如果没有）
    if not has_explanation:
        explanation = await generate_ai_explanation(match_data, pred, features_dict)
        if explanation:
            await conn.execute("""
                UPDATE predictions
                SET ai_explanation = $1
                WHERE match_id = $2
            """, explanation, match_id)
            print(f"  ✓ AI说明已保存")
    else:
        print(f"  ⊙ 已有AI说明")

    # 生成媒体分析（如果没有）
    if not has_media:
        media = await generate_media_analysis(
            match_data, pred, home_pi_dict, away_pi_dict,
            [dict(r) for r in h2h_list],
            [dict(r) for r in home_form],
            [dict(r) for r in away_form]
        )
        if media:
            await conn.execute("""
                INSERT INTO media_analysis (match_id, summary, generated_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (match_id) DO UPDATE
                SET summary = $2, generated_at = $3
            """, match_id, media["summary"], media["generated_at"])
            print(f"  ✓ 媒体分析已保存")
    else:
        print(f"  ⊙ 已有媒体分析")


async def main():
    """主函数：扫描未来比赛并生成AI分析"""
    print("=" * 60)
    print("开始生成AI分析")
    print("=" * 60)

    if not ANTHROPIC_API_KEY:
        print("错误：未设置 ANTHROPIC_API_KEY 环境变量")
        return

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # 查询未来7天的比赛，且缺少AI分析的
        now = datetime.now()
        future_date = now + timedelta(days=7)

        matches = await conn.fetch("""
            SELECT DISTINCT m.id
            FROM matches_live m
            LEFT JOIN predictions p ON m.id = p.match_id
            LEFT JOIN media_analysis ma ON m.id = ma.match_id
            WHERE m.date > $1
              AND m.date < $2
              AND m.home_goals IS NULL
              AND (p.ai_explanation IS NULL OR ma.match_id IS NULL)
            ORDER BY m.date
        """, now, future_date)

        print(f"\n找到 {len(matches)} 场需要生成AI分析的比赛\n")

        for i, match in enumerate(matches, 1):
            print(f"[{i}/{len(matches)}]", end=" ")
            await process_match(conn, match["id"])

            # 避免API限流
            if i < len(matches):
                await asyncio.sleep(2)

        print("\n" + "=" * 60)
        print(f"完成！共处理 {len(matches)} 场比赛")
        print("=" * 60)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
