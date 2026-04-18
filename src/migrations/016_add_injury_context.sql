-- 伤病/停赛数据缓存表
CREATE TABLE IF NOT EXISTS match_injury_context (
    id SERIAL PRIMARY KEY,
    match_live_id INT REFERENCES matches_live(id) ON DELETE CASCADE,
    team VARCHAR(100) NOT NULL,          -- canonical英文队名
    player_name VARCHAR(100) NOT NULL,
    injury_type VARCHAR(50),             -- 'Missing Fixture' / 'Questionable'
    reason VARCHAR(200),                 -- 'Hamstring Injury', 'Suspension', etc.
    fixture_date DATE,
    fetched_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (match_live_id, team, player_name)
);

CREATE INDEX IF NOT EXISTS idx_injury_match ON match_injury_context(match_live_id);
CREATE INDEX IF NOT EXISTS idx_injury_fetched ON match_injury_context(fetched_at);
