// API types for Augur

export interface Match {
  id: number;
  date: string;
  league: string;
  home_team: string;
  away_team: string;
  home_goals: number | null;
  away_goals: number | null;
  odds_home: number | null;
  odds_draw: number | null;
  odds_away: number | null;
}

export interface Prediction {
  match_id: number;
  home_team: string;
  away_team: string;
  match_date: string;
  pred_home_win: number;
  pred_draw: number;
  pred_away_win: number;
  model_name: string;
  predicted_at: string;
}

export interface MatchWithPrediction extends Match {
  prediction: Prediction | null;
  value_signal?: {
    home: number;
    draw: number;
    away: number;
  };
}

export interface TeamStats {
  name: string;
  recent_form: ("W" | "D" | "L")[];
  points_5: number;
  goals_scored_5: number;
  goals_conceded_5: number;
  pi_attack: number;
  pi_defense: number;
}

export interface HeadToHead {
  total: number;
  home_wins: number;
  draws: number;
  away_wins: number;
  avg_goals: number;
}

export interface MatchDetail {
  match: Match;
  prediction: Prediction | null;
  home_stats: TeamStats | null;
  away_stats: TeamStats | null;
  h2h: HeadToHead | null;
}
