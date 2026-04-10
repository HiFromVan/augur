// Mock data for development - no backend needed yet

import type { Match, Prediction, MatchDetail, TeamStats, HeadToHead } from "./types";

export const mockMatches: Match[] = [
  {
    id: 1,
    date: "2026-04-03T21:00:00",
    league: "PL",
    home_team: "Arsenal FC",
    away_team: "Manchester City FC",
    home_goals: null,
    away_goals: null,
    odds_home: null,
    odds_draw: null,
    odds_away: null,
  },
  {
    id: 2,
    date: "2026-04-03T21:00:00",
    league: "PL",
    home_team: "Liverpool FC",
    away_team: "Chelsea FC",
    home_goals: null,
    away_goals: null,
    odds_home: null,
    odds_draw: null,
    odds_away: null,
  },
  {
    id: 3,
    date: "2026-04-03T21:00:00",
    league: "CL",
    home_team: "Real Madrid CF",
    away_team: "Arsenal FC",
    home_goals: null,
    away_goals: null,
    odds_home: null,
    odds_draw: null,
    odds_away: null,
  },
  {
    id: 4,
    date: "2026-04-03T21:00:00",
    league: "BSA",
    home_team: "Palmeiras",
    away_team: "Flamengo",
    home_goals: null,
    away_goals: null,
    odds_home: null,
    odds_draw: null,
    odds_away: null,
  },
  {
    id: 5,
    date: "2026-04-03T21:00:00",
    league: "ELC",
    home_team: "Leeds United",
    away_team: "Burnley FC",
    home_goals: null,
    away_goals: null,
    odds_home: null,
    odds_draw: null,
    odds_away: null,
  },
  {
    id: 6,
    date: "2026-04-02T21:00:00",
    league: "PL",
    home_team: "Tottenham Hotspur FC",
    away_team: "Manchester United FC",
    home_goals: 2,
    away_goals: 1,
    odds_home: null,
    odds_draw: null,
    odds_away: null,
  },
  {
    id: 7,
    date: "2026-04-02T21:00:00",
    league: "PL",
    home_team: "Newcastle United FC",
    away_team: "Brighton & Hove Albion FC",
    home_goals: 3,
    away_goals: 2,
    odds_home: null,
    odds_draw: null,
    odds_away: null,
  },
];

const mockPredictions: Record<number, Prediction> = {
  1: {
    match_id: 1,
    home_team: "Arsenal FC",
    away_team: "Manchester City FC",
    match_date: "2026-04-03T21:00:00",
    pred_home_win: 0.42,
    pred_draw: 0.27,
    pred_away_win: 0.31,
    model_name: "catboost_v1",
    predicted_at: "2026-04-03T10:00:00",
  },
  2: {
    match_id: 2,
    home_team: "Liverpool FC",
    away_team: "Chelsea FC",
    match_date: "2026-04-03T21:00:00",
    pred_home_win: 0.55,
    pred_draw: 0.25,
    pred_away_win: 0.20,
    model_name: "catboost_v1",
    predicted_at: "2026-04-03T10:00:00",
  },
  3: {
    match_id: 3,
    home_team: "Real Madrid CF",
    away_team: "Arsenal FC",
    match_date: "2026-04-03T21:00:00",
    pred_home_win: 0.38,
    pred_draw: 0.25,
    pred_away_win: 0.37,
    model_name: "catboost_v1",
    predicted_at: "2026-04-03T10:00:00",
  },
  4: {
    match_id: 4,
    home_team: "Palmeiras",
    away_team: "Flamengo",
    match_date: "2026-04-03T21:00:00",
    pred_home_win: 0.45,
    pred_draw: 0.28,
    pred_away_win: 0.27,
    model_name: "catboost_v1",
    predicted_at: "2026-04-03T10:00:00",
  },
  5: {
    match_id: 5,
    home_team: "Leeds United",
    away_team: "Burnley FC",
    match_date: "2026-04-03T21:00:00",
    pred_home_win: 0.35,
    pred_draw: 0.30,
    pred_away_win: 0.35,
    model_name: "catboost_v1",
    predicted_at: "2026-04-03T10:00:00",
  },
};

export function getMockMatches(): Match[] {
  return mockMatches;
}

export function getMockMatchDetail(id: number): MatchDetail {
  const match = mockMatches.find((m) => m.id === id) || mockMatches[0];
  const prediction = mockPredictions[id] || null;

  const homeStats: TeamStats = {
    name: match.home_team,
    recent_form: ["W", "W", "D", "L", "W"],
    points_5: 10,
    goals_scored_5: 1.6,
    goals_conceded_5: 0.8,
    pi_attack: 1025.3,
    pi_defense: 997.1,
  };

  const awayStats: TeamStats = {
    name: match.away_team,
    recent_form: ["W", "L", "W", "D", "L"],
    points_5: 7,
    goals_scored_5: 1.4,
    goals_conceded_5: 1.2,
    pi_attack: 1018.7,
    pi_defense: 1002.5,
  };

  const h2h: HeadToHead = {
    total: 10,
    home_wins: 4,
    draws: 3,
    away_wins: 3,
    avg_goals: 2.6,
  };

  return {
    match,
    prediction,
    home_stats: homeStats,
    away_stats: awayStats,
    h2h,
  };
}
