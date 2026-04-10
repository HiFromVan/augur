-- 添加比赛状态字段
ALTER TABLE matches ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending';

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_date_status ON matches(date, status);

-- 更新现有数据：根据比分判断状态
UPDATE matches
SET status = CASE
    WHEN home_goals IS NOT NULL AND away_goals IS NOT NULL THEN 'finished'
    WHEN date < NOW() - INTERVAL '2 hours' THEN 'finished'  -- 开赛超过2小时视为已结束
    WHEN date < NOW() THEN 'live'  -- 已开赛但未结束
    ELSE 'pending'  -- 未开赛
END
WHERE status = 'pending' OR status IS NULL;
