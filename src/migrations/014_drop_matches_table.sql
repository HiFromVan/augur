-- Migration 014: 删除旧 matches 表，重建依赖视图

-- 删除依赖旧 matches 表的视图
DROP VIEW IF EXISTS data_quality_stats;
DROP VIEW IF EXISTS prediction_accuracy_view;

-- 删除旧表（CASCADE 同时删除依赖的外键等）
DROP TABLE IF EXISTS matches CASCADE;

-- 重建 prediction_accuracy_by_league 视图（指向 matches_live）
CREATE OR REPLACE VIEW prediction_accuracy_by_league AS
SELECT
    m.league,
    COUNT(*) as total_predictions,
    COUNT(*) FILTER (WHERE pr.is_correct = true) as correct_predictions,
    ROUND((COUNT(*) FILTER (WHERE pr.is_correct = true)::NUMERIC / NULLIF(COUNT(*), 0) * 100)::NUMERIC, 2) as accuracy_percentage,
    ROUND(AVG(pr.rps_score)::NUMERIC, 4) as avg_rps,
    COUNT(*) FILTER (WHERE pr.score_exact_match = true) as exact_score_matches
FROM prediction_records pr
JOIN matches_live m ON pr.match_live_id = m.id
WHERE pr.evaluated_at IS NOT NULL
  AND m.league IS NOT NULL
  AND m.league != ''
GROUP BY m.league
HAVING COUNT(*) >= 1
ORDER BY total_predictions DESC;

-- 重建 data_quality_stats 视图（指向 matches_live）
CREATE OR REPLACE VIEW data_quality_stats AS
SELECT
    (SELECT MAX(updated_at) FROM matches_live WHERE home_goals IS NOT NULL) AS last_result_update,
    (SELECT COUNT(*) FROM matches_live
     WHERE status = 'pending' AND date < NOW() - INTERVAL '24 hours') AS missing_results_count,
    (SELECT COUNT(*) FROM prediction_records pr
     JOIN matches_live m ON m.id = pr.match_live_id
     WHERE pr.evaluated_at IS NULL AND m.date < NOW()) AS pending_evaluations,
    (SELECT COUNT(*) FROM prediction_records
     WHERE evaluated_at IS NOT NULL
       AND predicted_at > NOW() - INTERVAL '7 days') AS recent_evaluations,
    (SELECT COUNT(*) FROM matches_live
     WHERE status = 'finished' AND home_goals IS NULL) AS finished_without_score,
    0 AS evaluated_without_actual;
