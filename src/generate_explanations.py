"""
批量生成比赛预测说明
使用 Claude API 为所有未生成说明的比赛生成 AI 分析
"""

import asyncio
import asyncpg
import os
import httpx
from anthropic import Anthropic
from datetime import datetime

# 数据库配置
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://augur:augur@localhost:5432/augur"
)

# API 配置
API_BASE = os.getenv("API_BASE", "http://localhost:8000")

# Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


async def get_match_prediction(match_id: int):
    """从 API 获取比赛预测"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{API_BASE}/api/match/{match_id}")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"  ⚠️  API 返回错误: {response.status_code}")
                return None
        except Exception as e:
            print(f"  ⚠️  API 调用失败: {e}")
            return None


def generate_explanation_prompt(data: dict) -> str:
    """生成 AI 提示词"""

    # 格式化近期表现
    def format_form(form_list):
        if not form_list:
            return "暂无数据"
        results = []
        for f in form_list[:5]:
            result_map = {'W': '胜', 'D': '平', 'L': '负'}
            result = result_map.get(f.get('result', ''), '?')
            location = '主' if f.get('is_home') else '客'
            results.append(f"{result} {f.get('goals_for', 0)}-{f.get('goals_against', 0)} vs {f.get('opponent', '?')} ({location})")
        return " | ".join(results)

    home_form_str = format_form(data.get('home_form', []))
    away_form_str = format_form(data.get('away_form', []))

    # 计算价值
    pred_home = data.get('pred_home_win', 0)
    pred_draw = data.get('pred_draw', 0)
    pred_away = data.get('pred_away_win', 0)
    implied_home = data.get('implied_home', 0)
    implied_draw = data.get('implied_draw', 0)
    implied_away = data.get('implied_away', 0)

    value_home = pred_home - implied_home
    value_draw = pred_draw - implied_draw
    value_away = pred_away - implied_away

    prompt = f"""你是一位专业的足球分析师。请为以下比赛生成一段简洁的预测分析说明（150-200字）。

比赛信息：
- 对阵：{data.get('home_team', '?')} vs {data.get('away_team', '?')}
- 联赛：{data.get('league', '?')}
- 日期：{data.get('date', '?')}

AI 预测：
- 主胜：{pred_home:.1%}
- 平局：{pred_draw:.1%}
- 客胜：{pred_away:.1%}
- 预测比分：{data.get('pred_score_home', '?')}-{data.get('pred_score_away', '?')}
- 预期进球：主队 {data.get('expected_goals_home', 0):.2f}，客队 {data.get('expected_goals_away', 0):.2f}

市场赔率（隐含概率）：
- 主胜：{implied_home:.1%}
- 平局：{implied_draw:.1%}
- 客胜：{implied_away:.1%}

价值分析：
- 主胜价值：{value_home:+.1%}
- 平局价值：{value_draw:+.1%}
- 客胜价值：{value_away:+.1%}

近期表现：
- {data.get('home_team', '?')}（主队）：{home_form_str}
- {data.get('away_team', '?')}（客队）：{away_form_str}

请生成一段专业、客观的分析说明，包括：
1. 双方实力对比和近期状态
2. 预测结果的主要依据
3. 如果有价值投注机会（价值 > 3%），重点说明
4. 比赛的关键因素

要求：
- 语言简洁专业，150-200字
- 使用中文
- 不要使用"我认为"等主观表达
- 直接输出分析内容，不要加标题或前缀
"""

    return prompt


async def generate_explanation(match_id: int, data: dict) -> str:
    """调用 Claude API 生成说明"""
    if not anthropic_client:
        return "AI 服务暂时不可用"

    try:
        prompt = generate_explanation_prompt(data)

        response = anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=500,
            temperature=0.7,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        explanation = response.content[0].text.strip()
        return explanation

    except Exception as e:
        print(f"  ❌ 生成说明失败: {e}")
        return None


async def save_explanation(conn, match_id: int, explanation: str):
    """保存说明到数据库"""
    await conn.execute("""
        UPDATE matches_live
        SET ai_explanation = $1,
            explanation_generated_at = $2
        WHERE id = $3
    """, explanation, datetime.now(), match_id)


async def process_matches(limit: int = 10, regenerate: bool = False):
    """批量处理比赛"""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # 获取需要生成说明的比赛
        if regenerate:
            query = """
                SELECT id FROM matches_live
                WHERE home_goals IS NULL
                ORDER BY date ASC
                LIMIT $1
            """
        else:
            query = """
                SELECT id FROM matches_live
                WHERE home_goals IS NULL
                  AND ai_explanation IS NULL
                ORDER BY date ASC
                LIMIT $1
            """

        matches = await conn.fetch(query, limit)

        print(f"找到 {len(matches)} 场比赛需要生成说明\n")

        success_count = 0
        fail_count = 0

        for i, match in enumerate(matches, 1):
            match_id = match['id']
            print(f"[{i}/{len(matches)}] 处理比赛 ID: {match_id}")

            # 从 API 获取预测数据
            data = await get_match_prediction(match_id)
            if not data:
                print(f"  ❌ 未能获取预测数据\n")
                fail_count += 1
                continue

            print(f"  {data.get('home_team', '?')} vs {data.get('away_team', '?')}")

            # 生成说明
            explanation = await generate_explanation(match_id, data)
            if not explanation:
                print(f"  ❌ 生成失败\n")
                fail_count += 1
                continue

            # 保存到数据库
            await save_explanation(conn, match_id, explanation)

            print(f"  ✓ 已保存说明 ({len(explanation)} 字)")
            print(f"  预览: {explanation[:80]}...\n")

            success_count += 1

            # 避免 API 限流
            await asyncio.sleep(1)

        print(f"\n{'='*60}")
        print(f"完成！成功: {success_count}, 失败: {fail_count}")
        print(f"{'='*60}")

    finally:
        await conn.close()


if __name__ == "__main__":
    import sys

    # 解析参数
    limit = 10
    regenerate = False

    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help']:
            print("用法: python generate_explanations.py [数量] [--regenerate]")
            print("  数量: 要处理的比赛数量 (默认: 10)")
            print("  --regenerate: 重新生成已有说明的比赛")
            sys.exit(0)
        try:
            limit = int(sys.argv[1])
        except ValueError:
            print("错误: 数量必须是整数")
            sys.exit(1)

    if len(sys.argv) > 2 and sys.argv[2] == '--regenerate':
        regenerate = True

    print(f"开始批量生成预测说明 (limit={limit}, regenerate={regenerate})")
    asyncio.run(process_matches(limit=limit, regenerate=regenerate))
