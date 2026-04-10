-- Migration 013: 比赛数据分层架构
-- matches_history: 训练专用（英文队名，fdco 为主，有赔率）
-- matches_live:    即时专用（中文队名，fivehundred 为主，永久保留）

-- ============ 1. matches_history ============

CREATE TABLE IF NOT EXISTS matches_history (
    id              SERIAL PRIMARY KEY,
    date            TIMESTAMP NOT NULL,
    league          VARCHAR(20),
    home_team       VARCHAR(100) NOT NULL,
    away_team       VARCHAR(100) NOT NULL,
    home_goals      INT,
    away_goals      INT,
    result          VARCHAR(10),   -- home_win / draw / away_win
    odds_home       FLOAT,
    odds_draw       FLOAT,
    odds_away       FLOAT,
    odds_asian_home     FLOAT,
    odds_asian_handicap FLOAT,
    odds_asian_away     FLOAT,
    odds_ou_line        FLOAT,
    odds_ou_over        FLOAT,
    odds_ou_under       FLOAT,
    source          VARCHAR(30),   -- fdco / zqcf / footballdata
    source_match_id VARCHAR(100),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (home_team, away_team, date)
);

CREATE INDEX IF NOT EXISTS idx_mh_date        ON matches_history(date);
CREATE INDEX IF NOT EXISTS idx_mh_league      ON matches_history(league);
CREATE INDEX IF NOT EXISTS idx_mh_home        ON matches_history(home_team, date DESC);
CREATE INDEX IF NOT EXISTS idx_mh_away        ON matches_history(away_team, date DESC);
CREATE INDEX IF NOT EXISTS idx_mh_h2h         ON matches_history(home_team, away_team, date);
CREATE INDEX IF NOT EXISTS idx_mh_odds        ON matches_history(odds_home) WHERE odds_home IS NOT NULL;

-- ============ 2. matches_live ============

CREATE TABLE IF NOT EXISTS matches_live (
    id              SERIAL PRIMARY KEY,
    date            TIMESTAMP NOT NULL,
    league          VARCHAR(50),
    home_team       VARCHAR(100) NOT NULL,
    away_team       VARCHAR(100) NOT NULL,
    home_goals      INT,
    away_goals      INT,
    result          VARCHAR(10),
    odds_home       FLOAT,
    odds_draw       FLOAT,
    odds_away       FLOAT,
    odds_asian_home     FLOAT,
    odds_asian_handicap FLOAT,
    odds_asian_away     FLOAT,
    odds_ou_line        FLOAT,
    odds_ou_over        FLOAT,
    odds_ou_under       FLOAT,
    status          VARCHAR(20) DEFAULT 'scheduled',  -- scheduled/pending/live/finished
    source          VARCHAR(30) DEFAULT 'fivehundred',
    source_match_id VARCHAR(100),
    ai_explanation              TEXT,
    ai_explanation_generated_at TIMESTAMP,
    media_analysis              TEXT,
    media_analysis_generated_at TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (home_team, away_team, date)
);

CREATE INDEX IF NOT EXISTS idx_ml_date        ON matches_live(date);
CREATE INDEX IF NOT EXISTS idx_ml_status      ON matches_live(status);
CREATE INDEX IF NOT EXISTS idx_ml_source_id   ON matches_live(source, source_match_id);
CREATE INDEX IF NOT EXISTS idx_ml_home        ON matches_live(home_team, date DESC);
CREATE INDEX IF NOT EXISTS idx_ml_away        ON matches_live(away_team, date DESC);

-- ============ 3. match_sources（多数据源原始记录）============

CREATE TABLE IF NOT EXISTS match_sources (
    id              SERIAL PRIMARY KEY,
    match_id        INT NOT NULL,
    match_table     VARCHAR(10) NOT NULL,  -- 'history' | 'live'
    source          VARCHAR(30) NOT NULL,
    source_match_id VARCHAR(100),
    source_home_team VARCHAR(100),
    source_away_team VARCHAR(100),
    raw_data        JSONB,
    scraped_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (match_table, match_id, source)
);

CREATE INDEX IF NOT EXISTS idx_ms_match   ON match_sources(match_table, match_id);
CREATE INDEX IF NOT EXISTS idx_ms_source  ON match_sources(source, source_match_id);

-- ============ 4. 迁移现有数据 ============

-- 4a. fdco 历史数据 → matches_history
INSERT INTO matches_history (
    date, league, home_team, away_team,
    home_goals, away_goals, result,
    odds_home, odds_draw, odds_away,
    odds_asian_home, odds_asian_handicap, odds_asian_away,
    odds_ou_line, odds_ou_over, odds_ou_under,
    source, source_match_id, created_at, updated_at
)
SELECT
    date, league, home_team, away_team,
    home_goals, away_goals, result,
    odds_home, odds_draw, odds_away,
    odds_asian_home, odds_asian_handicap, odds_asian_away,
    odds_ou_line, odds_ou_over, odds_ou_under,
    source, source_match_id, created_at, updated_at
FROM matches
WHERE source = 'fdco'
ON CONFLICT (home_team, away_team, date) DO UPDATE SET
    odds_home           = COALESCE(EXCLUDED.odds_home, matches_history.odds_home),
    odds_draw           = COALESCE(EXCLUDED.odds_draw, matches_history.odds_draw),
    odds_away           = COALESCE(EXCLUDED.odds_away, matches_history.odds_away),
    odds_asian_home     = COALESCE(EXCLUDED.odds_asian_home, matches_history.odds_asian_home),
    odds_asian_handicap = COALESCE(EXCLUDED.odds_asian_handicap, matches_history.odds_asian_handicap),
    odds_asian_away     = COALESCE(EXCLUDED.odds_asian_away, matches_history.odds_asian_away),
    odds_ou_line        = COALESCE(EXCLUDED.odds_ou_line, matches_history.odds_ou_line),
    odds_ou_over        = COALESCE(EXCLUDED.odds_ou_over, matches_history.odds_ou_over),
    odds_ou_under       = COALESCE(EXCLUDED.odds_ou_under, matches_history.odds_ou_under),
    updated_at          = NOW();

-- 4b. fivehundred 数据 → matches_live（全部，不限时间）
INSERT INTO matches_live (
    date, league, home_team, away_team,
    home_goals, away_goals, result,
    odds_home, odds_draw, odds_away,
    status, source, source_match_id,
    ai_explanation, ai_explanation_generated_at,
    media_analysis, media_analysis_generated_at,
    created_at, updated_at
)
SELECT
    date, league, home_team, away_team,
    home_goals, away_goals, result,
    odds_home, odds_draw, odds_away,
    COALESCE(status, 'scheduled'), source, source_match_id,
    ai_explanation, ai_explanation_generated_at,
    media_analysis, media_analysis_generated_at,
    created_at, updated_at
FROM matches
WHERE source = 'fivehundred'
ON CONFLICT (home_team, away_team, date) DO UPDATE SET
    odds_home       = COALESCE(EXCLUDED.odds_home, matches_live.odds_home),
    odds_draw       = COALESCE(EXCLUDED.odds_draw, matches_live.odds_draw),
    odds_away       = COALESCE(EXCLUDED.odds_away, matches_live.odds_away),
    home_goals      = COALESCE(EXCLUDED.home_goals, matches_live.home_goals),
    away_goals      = COALESCE(EXCLUDED.away_goals, matches_live.away_goals),
    status          = EXCLUDED.status,
    updated_at      = NOW();

-- 4c. 迁移 prediction_records 外键到 matches_live
-- 先加新列，再回填，最后切换
ALTER TABLE prediction_records
    ADD COLUMN IF NOT EXISTS match_live_id INT REFERENCES matches_live(id);

UPDATE prediction_records pr
SET match_live_id = ml.id
FROM matches m
JOIN matches_live ml ON (ml.home_team = m.home_team AND ml.away_team = m.away_team AND ml.date = m.date)
WHERE pr.match_id = m.id
  AND m.source = 'fivehundred';

-- 4d. 迁移 odds_history 外键到 matches_live
ALTER TABLE odds_history
    ADD COLUMN IF NOT EXISTS match_live_id INT REFERENCES matches_live(id);

UPDATE odds_history oh
SET match_live_id = ml.id
FROM matches m
JOIN matches_live ml ON (ml.home_team = m.home_team AND ml.away_team = m.away_team AND ml.date = m.date)
WHERE oh.match_id = m.id
  AND m.source = 'fivehundred';
