-- 性能优化：添加数据库索引

-- 1. 为历史交锋查询添加索引
CREATE INDEX IF NOT EXISTS idx_matches_teams_date ON matches(home_team, away_team, date) WHERE home_goals IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_matches_teams_date_reverse ON matches(away_team, home_team, date) WHERE home_goals IS NOT NULL;

-- 2. 为近期战绩查询添加索引
CREATE INDEX IF NOT EXISTS idx_matches_team_date ON matches(home_team, date DESC) WHERE home_goals IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_matches_away_team_date ON matches(away_team, date DESC) WHERE home_goals IS NOT NULL;

-- 3. 为比赛日期查询添加索引
CREATE INDEX IF NOT EXISTS idx_matches_date_league ON matches(date, league);

COMMENT ON INDEX idx_matches_teams_date IS '加速历史交锋查询';
COMMENT ON INDEX idx_matches_team_date IS '加速近期战绩查询';
