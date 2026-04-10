-- 修复 batch_evaluate_predictions 函数，改用 matches_live 表
-- 修复 prediction_accuracy_stats 视图，total_predictions 包含所有预测

-- 重写评估函数
CREATE OR REPLACE FUNCTION batch_evaluate_predictions(limit_count INTEGER DEFAULT 100)
RETURNS TABLE(evaluated_count INTEGER, failed_count INTEGER) AS $$
DECLARE
    match_record RECORD;
    v_evaluated INTEGER := 0;
    v_failed INTEGER := 0;
BEGIN
    FOR match_record IN
        SELECT DISTINCT pr.match_live_id
        FROM prediction_records pr
        JOIN matches_live m ON pr.match_live_id = m.id
        WHERE pr.evaluated_at IS NULL
          AND m.home_goals IS NOT NULL
          AND m.away_goals IS NOT NULL
        LIMIT limit_count
    LOOP
        BEGIN
            UPDATE prediction_records pr
            SET
                actual_home = m.home_goals,
                actual_away = m.away_goals,
                is_correct = (
                    CASE
                        WHEN pr.pred_home > pr.pred_draw AND pr.pred_home > pr.pred_away THEN 'home'
                        WHEN pr.pred_draw > pr.pred_home AND pr.pred_draw > pr.pred_away THEN 'draw'
                        ELSE 'away'
                    END
                ) = (
                    CASE
                        WHEN m.home_goals > m.away_goals THEN 'home'
                        WHEN m.home_goals = m.away_goals THEN 'draw'
                        ELSE 'away'
                    END
                ),
                score_exact_match = (pr.pred_score_home = m.home_goals AND pr.pred_score_away = m.away_goals),
                score_diff = ABS(pr.pred_score_home - m.home_goals) + ABS(pr.pred_score_away - m.away_goals),
                evaluated_at = NOW()
            FROM matches_live m
            WHERE pr.match_live_id = match_record.match_live_id
              AND m.id = match_record.match_live_id
              AND pr.evaluated_at IS NULL;
            v_evaluated := v_evaluated + 1;
        EXCEPTION WHEN OTHERS THEN
            v_failed := v_failed + 1;
        END;
    END LOOP;
    RETURN QUERY SELECT v_evaluated, v_failed;
END;
$$ LANGUAGE plpgsql;

-- 修复 prediction_accuracy_stats 视图，total_predictions 包含所有预测
CREATE OR REPLACE VIEW prediction_accuracy_stats AS
SELECT
    (SELECT COUNT(*) FROM prediction_records) AS total_predictions,
    COUNT(*) FILTER (WHERE is_correct = true) AS correct_predictions,
    ROUND(
        (COUNT(*) FILTER (WHERE is_correct = true))::numeric /
        NULLIF(COUNT(*) FILTER (WHERE evaluated_at IS NOT NULL), 0)::numeric * 100,
        2
    ) AS accuracy_percentage,
    ROUND(AVG(rps_score)::numeric, 4) AS avg_rps,
    COUNT(*) FILTER (WHERE score_exact_match = true) AS exact_score_matches,
    ROUND(AVG(ABS(score_diff)), 2) AS avg_score_diff
FROM prediction_records
WHERE evaluated_at IS NOT NULL;
