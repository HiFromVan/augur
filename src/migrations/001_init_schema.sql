-- Augur 数据库迁移脚本 v001
-- 创建完整表结构

-- 1. leagues 联赛表
CREATE TABLE IF NOT EXISTS leagues (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(20)  NOT NULL UNIQUE,
    name_cn         VARCHAR(50),
    name_en         VARCHAR(50),
    country         VARCHAR(30),
    source_config   JSONB,
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 2. team_aliases 球队别名表（核心映射表）
CREATE TABLE IF NOT EXISTS team_aliases (
    id              SERIAL PRIMARY KEY,
    team_id         INT REFERENCES teams(id) ON DELETE CASCADE,
    source          VARCHAR(30)  NOT NULL,
    alias           VARCHAR(100) NOT NULL,
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(source, alias)
);

-- 3. matches 表扩展（添加 status, result, updated_at）
ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'scheduled',
    ADD COLUMN IF NOT EXISTS result VARCHAR(10),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- 添加 canonical 外键（先加列，约束等别名表有数据后再加）
ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS canonical_home_id INT,
    ADD COLUMN IF NOT EXISTS canonical_away_id INT;

-- 4. match_events 比赛事件表
CREATE TABLE IF NOT EXISTS match_events (
    id              SERIAL PRIMARY KEY,
    match_id        INT REFERENCES matches(id) ON DELETE CASCADE,
    event_type      VARCHAR(20) NOT NULL,
    minute          INT,
    team_id         INT REFERENCES teams(id),
    player_name     VARCHAR(100),
    detail          VARCHAR(50),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 5. player_stats 球员统计
CREATE TABLE IF NOT EXISTS player_stats (
    id              SERIAL PRIMARY KEY,
    player_name     VARCHAR(100) NOT NULL,
    team_id         INT REFERENCES teams(id),
    league_code     VARCHAR(20),
    season          VARCHAR(10),
    match_id        INT REFERENCES matches(id),
    appearances     INT DEFAULT 0,
    minutes         INT DEFAULT 0,
    goals           INT DEFAULT 0,
    assists         INT DEFAULT 0,
    yellow_cards    INT DEFAULT 0,
    red_cards       INT DEFAULT 0,
    shots           INT DEFAULT 0,
    shots_on_target INT DEFAULT 0,
    passes          INT DEFAULT 0,
    pass_accuracy   FLOAT DEFAULT 0,
    tackles         INT DEFAULT 0,
    interceptions   INT DEFAULT 0,
    fouls           INT DEFAULT 0,
    offsides        INT DEFAULT 0,
    saves           INT DEFAULT 0,
    clean_sheets    INT DEFAULT 0,
    source          VARCHAR(30) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(player_name, match_id, source)
);

-- 6. odds_history 赔率历史表（核心！历史 + 实时共用）
CREATE TABLE IF NOT EXISTS odds_history (
    id                  SERIAL PRIMARY KEY,
    match_id            INT REFERENCES matches(id) ON DELETE CASCADE,
    source              VARCHAR(30) NOT NULL,
    odds_home           FLOAT,
    odds_draw           FLOAT,
    odds_away           FLOAT,
    handicap            FLOAT,
    odds_handicap_home  FLOAT,
    odds_handicap_away  FLOAT,
    total_line          FLOAT,
    odds_over           FLOAT,
    odds_under          FLOAT,
    odds_type           VARCHAR(20) DEFAULT 'main',
    scraped_at          TIMESTAMP DEFAULT NOW(),
    match_time          TIMESTAMP,
    UNIQUE(match_id, source, odds_type, scraped_at)
);

-- 7. predictions 表扩展（添加 Value Betting 字段）
ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS pred_prob_sum FLOAT,
    ADD COLUMN IF NOT EXISTS confidence FLOAT,
    ADD COLUMN IF NOT EXISTS implied_home FLOAT,
    ADD COLUMN IF NOT EXISTS implied_draw FLOAT,
    ADD COLUMN IF NOT EXISTS implied_away FLOAT,
    ADD COLUMN IF NOT EXISTS value_home FLOAT,
    ADD COLUMN IF NOT EXISTS value_draw FLOAT,
    ADD COLUMN IF NOT EXISTS value_away FLOAT;

-- 8. scrapers 爬虫配置表
CREATE TABLE IF NOT EXISTS scrapers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50)  NOT NULL UNIQUE,
    adapter_class   VARCHAR(100) NOT NULL,
    base_url        TEXT,
    api_key         VARCHAR(200),
    config          JSONB,
    schedule_type   VARCHAR(20) DEFAULT 'interval',
    schedule_value  VARCHAR(50),
    enabled         BOOLEAN DEFAULT TRUE,
    last_run_at     TIMESTAMP,
    last_status     VARCHAR(20),
    last_error      TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- 9. scraper_runs 爬虫执行记录
CREATE TABLE IF NOT EXISTS scraper_runs (
    id              SERIAL PRIMARY KEY,
    scraper_name    VARCHAR(50) NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    status          VARCHAR(20) NOT NULL,
    records_fetched INT DEFAULT 0,
    error_message   TEXT,
    duration_secs   FLOAT
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_canonical_home ON matches(canonical_home_id);
CREATE INDEX IF NOT EXISTS idx_matches_canonical_away ON matches(canonical_away_id);
CREATE INDEX IF NOT EXISTS idx_team_aliases_team ON team_aliases(team_id);
CREATE INDEX IF NOT EXISTS idx_team_aliases_source ON team_aliases(source);
CREATE INDEX IF NOT EXISTS idx_odds_match ON odds_history(match_id);
CREATE INDEX IF NOT EXISTS idx_odds_scraped ON odds_history(scraped_at);
CREATE INDEX IF NOT EXISTS idx_odds_source ON odds_history(source);
CREATE INDEX IF NOT EXISTS idx_pred_match ON predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_events_match ON match_events(match_id);
CREATE INDEX IF NOT EXISTS idx_player_team ON player_stats(team_id);
CREATE INDEX IF NOT EXISTS idx_player_match ON player_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_runs_name ON scraper_runs(scraper_name);
CREATE INDEX IF NOT EXISTS idx_runs_started ON scraper_runs(started_at);

-- 插入默认联赛数据
INSERT INTO leagues (code, name_cn, name_en, country, active) VALUES
    ('PL', '英超', 'Premier League', 'England', TRUE),
    ('ELC', '英冠', 'EFL Championship', 'England', TRUE),
    ('ESP1', '西甲', 'La Liga', 'Spain', TRUE),
    ('ITA1', '意甲', 'Serie A', 'Italy', TRUE),
    ('GER1', '德甲', 'Bundesliga', 'Germany', TRUE),
    ('FRA1', '法甲', 'Ligue 1', 'France', TRUE),
    ('CL', '欧冠', 'Champions League', 'Europe', TRUE),
    ('EL', '欧联', 'Europa League', 'Europe', TRUE),
    ('BSA', '巴甲', 'Brasileirão', 'Brazil', TRUE)
ON CONFLICT (code) DO UPDATE SET
    name_cn = EXCLUDED.name_cn,
    name_en = EXCLUDED.name_en,
    active = EXCLUDED.active;

-- 注册 500 网爬虫
INSERT INTO scrapers (name, adapter_class, base_url, schedule_type, schedule_value, enabled) VALUES
    ('fivehundred', 'FiveHundredAdapter', 'https://trade.500.com/jczq/', 'interval', '3600', TRUE)
ON CONFLICT (name) DO UPDATE SET
    adapter_class = EXCLUDED.adapter_class,
    base_url = EXCLUDED.base_url,
    schedule_value = EXCLUDED.schedule_value,
    enabled = EXCLUDED.enabled,
    updated_at = NOW();
