-- 添加 AI 使用量跟踪表
CREATE TABLE IF NOT EXISTS ai_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    chat_count INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_usage_user_date ON ai_usage(user_id, date);

-- 创建检查使用限制的函数
CREATE OR REPLACE FUNCTION check_ai_usage_limit(p_user_id INTEGER)
RETURNS TABLE(
    can_use BOOLEAN,
    daily_count INTEGER,
    daily_limit INTEGER,
    monthly_tokens INTEGER,
    monthly_limit INTEGER,
    plan_code VARCHAR(20)
) AS $$
DECLARE
    v_daily_count INTEGER := 0;
    v_monthly_tokens INTEGER := 0;
    v_daily_limit INTEGER := 0;
    v_monthly_limit INTEGER := 0;
    v_plan_code VARCHAR(20) := 'trial';
BEGIN
    -- 获取用户订阅档位
    SELECT sp.plan_code INTO v_plan_code
    FROM users u
    JOIN subscriptions s ON s.user_id = u.id
    JOIN subscription_plans sp ON sp.plan_code = s.plan_code
    WHERE u.id = p_user_id
      AND s.status = 'active'
      AND s.end_date > NOW()
    ORDER BY s.end_date DESC
    LIMIT 1;

    -- 根据档位设置限制
    IF v_plan_code = 'basic_yearly' THEN
        v_daily_limit := 10;  -- 基础档每日 10 次
        v_monthly_limit := 100000;  -- 每月 10 万 tokens
    ELSIF v_plan_code = 'premium_yearly' THEN
        v_daily_limit := 100;  -- 高级档每日 100 次
        v_monthly_limit := 1000000;  -- 每月 100 万 tokens
    ELSE
        v_daily_limit := 0;  -- 试用期无 AI 对话
        v_monthly_limit := 0;
    END IF;

    -- 获取今日使用次数
    SELECT COALESCE(chat_count, 0) INTO v_daily_count
    FROM ai_usage
    WHERE user_id = p_user_id AND date = CURRENT_DATE;

    -- 获取本月使用 tokens
    SELECT COALESCE(SUM(tokens_used), 0) INTO v_monthly_tokens
    FROM ai_usage
    WHERE user_id = p_user_id
      AND date >= DATE_TRUNC('month', CURRENT_DATE);

    -- 返回结果
    RETURN QUERY SELECT
        (v_daily_count < v_daily_limit AND v_monthly_tokens < v_monthly_limit) as can_use,
        v_daily_count as daily_count,
        v_daily_limit as daily_limit,
        v_monthly_tokens as monthly_tokens,
        v_monthly_limit as monthly_limit,
        v_plan_code as plan_code;
END;
$$ LANGUAGE plpgsql;

-- 创建记录使用的函数
CREATE OR REPLACE FUNCTION record_ai_usage(
    p_user_id INTEGER,
    p_tokens INTEGER
) RETURNS VOID AS $$
BEGIN
    INSERT INTO ai_usage (user_id, date, chat_count, tokens_used)
    VALUES (p_user_id, CURRENT_DATE, 1, p_tokens)
    ON CONFLICT (user_id, date)
    DO UPDATE SET
        chat_count = ai_usage.chat_count + 1,
        tokens_used = ai_usage.tokens_used + p_tokens,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;
