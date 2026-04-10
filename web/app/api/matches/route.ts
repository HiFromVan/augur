import { NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000";

export async function GET() {
  try {
    const resp = await fetch(`${FASTAPI_URL}/api/matches`, {
      cache: 'no-store', // 不缓存，实时获取
    });

    if (!resp.ok) {
      throw new Error(`FastAPI error: ${resp.status}`);
    }

    const data = await resp.json();

    // 转换为前端 MatchCard 需要的格式
    const matches = data.matches.map((m: any) => ({
      id: m.id,
      date: m.date,
      league: m.league,
      league_cn: m.league_cn,
      home_team: m.home_team_cn || m.home_team,
      away_team: m.away_team_cn || m.away_team,
      home_goals: m.home_goals,
      away_goals: m.away_goals,
      odds_home: m.odds_home,
      odds_draw: m.odds_draw,
      odds_away: m.odds_away,
      // 预测和价值信号
      pred_home: m.pred_home,
      pred_draw: m.pred_draw,
      pred_away: m.pred_away,
      implied_home: m.implied_home,
      implied_draw: m.implied_draw,
      implied_away: m.implied_away,
      value_home: m.value_home,
      value_draw: m.value_draw,
      value_away: m.value_away,
      has_value: m.has_value,
      model_name: m.model_name,
      // AI 预测说明
      ai_explanation: m.ai_explanation,
      expected_goals_home: m.expected_goals_home,
      expected_goals_away: m.expected_goals_away,
    }));

    return NextResponse.json({ matches });
  } catch (err) {
    console.error("Failed to fetch from FastAPI:", err);
    return NextResponse.json({ error: "Failed to fetch matches" }, { status: 500 });
  }
}
