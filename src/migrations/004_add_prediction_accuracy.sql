-- 预测准确率系统数据库迁移

-- 1. 创建预测记录表
CREATE TABLE IF NOT EXISTS prediction_records (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,

    -- 预测数据
    pred_home FLOAT NOT NULL,
    pred_draw FLOAT NOT NULL,
    pred_away FLOAT NOT NULL,
    pred_score_home INTEGER,
    pred_score_away INTEGER,
    expected_goals_home FLOAT,
    expected_goals_away FLOAT,

    -- 实际结果
    actual_home INTEGER,
    actual_away INTEGER,

    -- 准确性指标
    is_correct BOOLEAN,  -- 胜平负是否预测正确
    score_exact_match BOOLEAN,  -- 比分是否完全正确
    score_diff INTEGER,  -- 比分差距（预测进球数 vs 实际进球数）
    rps_score FLOAT,  -- Ranked Probability Score

    -- 元数据
    model_name VARCHAR(50),
    predicted_at TIMESTAMP DEFAULT NOW(),
    evaluated_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS idx_prediction_records_match_id ON prediction_records(match_id);
CREATE INDEX IF NOT EXISTS idx_prediction_records_is_correct ON prediction_records(is_correct);
CREATE INDEX IF NOT EXISTS idx_prediction_records_predicted_at ON prediction_records(predicted_at);
CREATE INDEX IF NOT EXISTS idx_prediction_records_evaluated_at ON prediction_records(evaluated_at);

-- 3. 创建准确率统计视图
CREATE OR REPLACE VIEW prediction_accuracy_stats AS
SELECT
    COUNT(*) as total_predictions,
    COUNT(*) FILTER (WHERE is_correct = true) as correct_predictions,
    ROUND((COUNT(*) FILTER (WHERE is_correct = true)::NUMERIC / NULLIF(COUNT(*), 0) * 100)::NUMERIC, 2) as accuracy_percentage,
    ROUND(AVG(rps_score)::NUMERIC, 4) as avg_rps,
    COUNT(*) FILTER (WHERE score_exact_match = true) as exact_score_matches,
    ROUND(AVG(ABS(score_diff))::NUMERIC, 2) as avg_score_diff
FROM prediction_records
WHERE evaluated_at IS NOT NULL;

-- 4. 创建按日期统计的视图
CREATE OR REPLACE VIEW prediction_accuracy_by_date AS
SELECT
    DATE(predicted_at) as prediction_date,
    COUNT(*) as total_predictions,
    COUNT(*) FILTER (WHERE is_correct = true) as correct_predictions,
    ROUND((COUNT(*) FILTER (WHERE is_correct = true)::NUMERIC / NULLIF(COUNT(*), 0) * 100)::NUMERIC, 2) as accuracy_percentage,
    ROUND(AVG(rps_score)::NUMERIC, 4) as avg_rps
FROM prediction_records
WHERE evaluated_at IS NOT NULL
GROUP BY DATE(predicted_at)
ORDER BY prediction_date DESC;

-- 5. 创建函数：计算RPS (Ranked Probability Score)
CREATE OR REPLACE FUNCTION calculate_rps(
    p_pred_home FLOAT,
    p_pred_draw FLOAT,
    p_pred_away FLOAT,
    p_actual_home INTEGER,
    p_actual_away INTEGER
) RETURNS FLOAT AS $$
DECLARE
    actual_result INTEGER;  -- 0=主胜, 1=平, 2=客胜
    cum_pred FLOAT[];
    cum_actual FLOAT[];
    rps FLOAT := 0;
BEGIN
    -- 确定实际结果
    IF p_actual_home > p_actual_away THEN
        actual_result := 0;
    ELSIF p_actual_home = p_actual_away THEN
        actual_result := 1;
    ELSE
        actual_result := 2;
    END IF;

    -- 计算累积概率
    cum_pred := ARRAY[p_pred_home, p_pred_home + p_pred_draw, 1.0];
    cum_actual := ARRAY[
        CASE WHEN actual_result = 0 THEN 1.0 ELSE 0.0 END,
        CASE WHEN actual_result <= 1 THEN 1.0 ELSE 0.0 END,
        1.0
    ];

    -- 计算RPS
    FOR i IN 1..3 LOOP
        rps := rps + POWER(cum_pred[i] - cum_actual[i], 2);
    END LOOP;

    RETURN rps / 3.0;
END;
$$ LANGUAGE plpgsql;

-- 6. 创建函数：评估预测记录
CREATE OR REPLACE FUNCTION evaluate_prediction(p_match_id INTEGER)
RETURNS VOID AS $$
DECLARE
    v_match RECORD;
    v_pred RECORD;
    v_is_correct BOOLEAN;
    v_score_exact BOOLEAN;
    v_score_diff INTEGER;
    v_rps FLOAT;
BEGIN
    -- 获取比赛实际结果
    SELECT home_goals, away_goals INTO v_match
    FROM matches
    WHERE id = p_match_id AND home_goals IS NOT NULL;

    IF NOT FOUND THEN
        RETURN;  -- 比赛还没结束
    END IF;

    -- 获取预测记录
    SELECT * INTO v_pred
    FROM prediction_records
    WHERE match_id = p_match_id AND evaluated_at IS NULL
    ORDER BY predicted_at DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN;  -- 没有预测记录
    END IF;

    -- 判断胜平负是否正确
    v_is_correct := (
        (v_match.home_goals > v_match.away_goals AND v_pred.pred_home > v_pred.pred_draw AND v_pred.pred_home > v_pred.pred_away) OR
        (v_match.home_goals = v_match.away_goals AND v_pred.pred_draw > v_pred.pred_home AND v_pred.pred_draw > v_pred.pred_away) OR
        (v_match.home_goals < v_match.away_goals AND v_pred.pred_away > v_pred.pred_home AND v_pred.pred_away > v_pred.pred_draw)
    );

    -- 判断比分是否完全正确
    v_score_exact := (
        v_pred.pred_score_home = v_match.home_goals AND
        v_pred.pred_score_away = v_match.away_goals
    );

    -- 计算比分差距
    v_score_diff := ABS(COALESCE(v_pred.pred_score_home, 0) - v_match.home_goals) +
                    ABS(COALESCE(v_pred.pred_score_away, 0) - v_match.away_goals);

    -- 计算RPS
    v_rps := calculate_rps(
        v_pred.pred_home,
        v_pred.pred_draw,
        v_pred.pred_away,
        v_match.home_goals,
        v_match.away_goals
    );

    -- 更新预测记录
    UPDATE prediction_records
    SET
        actual_home = v_match.home_goals,
        actual_away = v_match.away_goals,
        is_correct = v_is_correct,
        score_exact_match = v_score_exact,
        score_diff = v_score_diff,
        rps_score = v_rps,
        evaluated_at = NOW()
    WHERE id = v_pred.id;
END;
$$ LANGUAGE plpgsql;
