-- 历史预测功能增强：索引和视图
-- 创建时间: 2026-04-09

-- ============ 索引优化 ============

-- 按日期查询预测记录
CREATE INDEX IF NOT EXISTS idx_prediction_records_predicted_at
ON prediction_records(predicted_at DESC);

-- 按准确性筛选
CREATE INDEX IF NOT EXISTS idx_prediction_records_is_correct
ON prediction_records(is_correct)
WHERE evaluated_at IS NOT NULL;

-- 按评估状态筛选
CREATE INDEX IF NOT EXISTS idx_prediction_records_evaluated
ON prediction_records(evaluated_at)
WHERE evaluated_at IS NULL;

-- 按联赛统计（matches 表）
CREATE INDEX IF NOT EXISTS idx_matches_league
ON matches(league)
WHERE league IS NOT NULL AND league != '';

-- 按比赛日期和状态查询
CREATE INDEX IF NOT EXISTS idx_matches_date_status
ON matches(date DESC, status);

-- ============ 视图：按联赛统计准确率 ============

CREATE OR REPLACE VIEW prediction_accuracy_by_league AS
SELECT
    m.league,
    COUNT(*) as total_predictions,
    COUNT(*) FILTER (WHERE pr.is_correct = true) as correct_predictions,
    ROUND((COUNT(*) FILTER (WHERE pr.is_correct = true)::NUMERIC / NULLIF(COUNT(*), 0) * 100)::NUMERIC, 2) as accuracy_percentage,
    ROUND(AVG(pr.rps_score)::NUMERIC, 4) as avg_rps,
    COUNT(*) FILTER (WHERE pr.score_exact_match = true) as exact_score_matches
FROM prediction_records pr
JOIN matches m ON pr.match_id = m.id
WHERE pr.evaluated_at IS NOT NULL
  AND m.league IS NOT NULL
  AND m.league != ''
GROUP BY m.league
HAVING COUNT(*) >= 5  -- 至少5场比赛才显示
ORDER BY total_predictions DESC;

-- ============ 视图：按周统计准确率 ============

CREATE OR REPLACE VIEW prediction_accuracy_by_week AS
SELECT
    DATE_TRUNC('week', predicted_at) as week_start,
    COUNT(*) as total_predictions,
    COUNT(*) FILTER (WHERE is_correct = true) as correct_predictions,
    ROUND((COUNT(*) FILTER (WHERE is_correct = true)::NUMERIC / NULLIF(COUNT(*), 0) * 100)::NUMERIC, 2) as accuracy_percentage,
    ROUND(AVG(rps_score)::NUMERIC, 4) as avg_rps,
    COUNT(*) FILTER (WHERE score_exact_match = true) as exact_score_matches
FROM prediction_records
WHERE evaluated_at IS NOT NULL
GROUP BY DATE_TRUNC('week', predicted_at)
ORDER BY week_start DESC;

-- ============ 视图：数据质量监控 ============

CREATE OR REPLACE VIEW data_quality_stats AS
SELECT
    -- 赛果更新统计
    (SELECT MAX(updated_at) FROM matches WHERE status = 'finished') as last_result_update,
    (SELECT COUNT(*) FROM matches
     WHERE status = 'pending'
     AND date < NOW() - INTERVAL '24 hours') as missing_results_count,

    -- 预测评估统计
    (SELECT COUNT(*) FROM prediction_records WHERE evaluated_at IS NULL) as pending_evaluations,
    (SELECT COUNT(*) FROM prediction_records
     WHERE evaluated_at IS NOT NULL
     AND evaluated_at > NOW() - INTERVAL '24 hours') as recent_evaluations,

    -- 异常数据统计
    (SELECT COUNT(*) FROM matches
     WHERE status = 'finished'
     AND (home_goals IS NULL OR away_goals IS NULL)) as finished_without_score,
    (SELECT COUNT(*) FROM prediction_records
     WHERE evaluated_at IS NOT NULL
     AND (actual_home IS NULL OR actual_away IS NULL)) as evaluated_without_actual;

-- ============ 函数：批量评估预测 ============

CREATE OR REPLACE FUNCTION batch_evaluate_predictions(limit_count INTEGER DEFAULT 100)
RETURNS TABLE(evaluated_count INTEGER, failed_count INTEGER) AS $$
DECLARE
    match_record RECORD;
    success_count INTEGER := 0;
    fail_count INTEGER := 0;
BEGIN
    -- 查找所有已完成但未评估的比赛
    FOR match_record IN
        SELECT DISTINCT pr.match_id
        FROM prediction_records pr
        JOIN matches m ON pr.match_id = m.id
        WHERE pr.evaluated_at IS NULL
          AND m.status = 'finished'
          AND m.home_goals IS NOT NULL
          AND m.away_goals IS NOT NULL
        LIMIT limit_count
    LOOP
        BEGIN
            -- 调用现有的评估函数
            PERFORM evaluate_prediction(match_record.match_id);
            success_count := success_count + 1;
        EXCEPTION WHEN OTHERS THEN
            fail_count := fail_count + 1;
            RAISE NOTICE 'Failed to evaluate match %: %', match_record.match_id, SQLERRM;
        END;
    END LOOP;

    RETURN QUERY SELECT success_count, fail_count;
END;
$$ LANGUAGE plpgsql;

-- ============ 注释 ============

COMMENT ON INDEX idx_prediction_records_predicted_at IS '按预测时间查询优化';
COMMENT ON INDEX idx_prediction_records_is_correct IS '按准确性筛选优化';
COMMENT ON INDEX idx_prediction_records_evaluated IS '查找待评估预测优化';
COMMENT ON INDEX idx_matches_league IS '按联赛统计优化';
COMMENT ON INDEX idx_matches_date_status IS '按日期和状态查询优化';

COMMENT ON VIEW prediction_accuracy_by_league IS '按联赛统计预测准确率';
COMMENT ON VIEW prediction_accuracy_by_week IS '按周统计预测准确率';
COMMENT ON VIEW data_quality_stats IS '数据质量监控统计';
COMMENT ON FUNCTION batch_evaluate_predictions IS '批量评估已完成比赛的预测';
