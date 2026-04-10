-- 添加比赛结果跟踪和预测准确率统计

-- 1. 确保 matches 表有必要的字段
ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS actual_result VARCHAR(10),
    ADD COLUMN IF NOT EXISTS result_updated_at TIMESTAMP;

-- 2. 创建预测结果对比视图
CREATE OR REPLACE VIEW prediction_accuracy_view AS
SELECT
    m.id,
    m.date,
    m.league,
    m.home_team,
    m.away_team,
    m.home_goals,
    m.away_goals,
    m.result,
    m.actual_result,
    pr.pred_home,
    pr.pred_draw,
    pr.pred_away,
    pr.pred_score_home,
    pr.pred_score_away,
    pr.created_at as prediction_time,
    pr.is_correct,
    pr.rps_score,
    CASE
        WHEN pr.pred_home > pr.pred_draw AND pr.pred_home > pr.pred_away THEN 'H'
        WHEN pr.pred_away > pr.pred_draw AND pr.pred_away > pr.pred_home THEN 'A'
        ELSE 'D'
    END as predicted_result
FROM matches m
LEFT JOIN prediction_records pr ON pr.match_id = m.id
WHERE m.home_goals IS NOT NULL;

-- 3. 创建索引
CREATE INDEX IF NOT EXISTS idx_matches_result ON matches(result) WHERE result IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_matches_date_result ON matches(date, result) WHERE result IS NOT NULL;

-- 4. 添加注释
COMMENT ON COLUMN matches.actual_result IS '实际比赛结果 (H/D/A)';
COMMENT ON COLUMN matches.result_updated_at IS '结果更新时间';
COMMENT ON VIEW prediction_accuracy_view IS '预测准确率统计视图';
