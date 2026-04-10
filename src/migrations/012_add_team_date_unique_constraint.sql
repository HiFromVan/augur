-- 添加 (home_team, away_team, date) 唯一约束，用于不同数据源间的比赛去重
-- 之前用 (source, source_match_id) 做唯一键，但不同源 match_num 不同，导致同比赛重复插入

-- 先删掉可能违反唯一约束的重复数据（保留最新那条）
DELETE FROM matches m1
USING matches m2
WHERE m1.id < m2.id
  AND m1.home_team = m2.home_team
  AND m1.away_team = m2.away_team
  AND m1.date::date = m2.date::date;

-- 添加唯一约束
DO $$
BEGIN
    -- 如果约束已存在会报错，忽略即可
    ALTER TABLE matches
    ADD CONSTRAINT matches_team_date_unique UNIQUE (home_team, away_team, date);
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'Constraint already exists, skipping';
END $$;
