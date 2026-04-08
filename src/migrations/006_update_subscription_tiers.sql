-- 更新订阅体系：基础档和高级档
-- 基础档 ¥1399/年 - 不含 AI 对话
-- 高级档 ¥2399/年 - 含 AI 对话及更多高级功能

-- 1. 添加 features 字段到 subscription_plans 表
ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS features JSONB DEFAULT '{}';

-- 2. 添加 tier 字段到 users 表（区分基础档和高级档）
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_plan_id INTEGER REFERENCES subscription_plans(id);

-- 3. 清空旧的套餐数据
DELETE FROM subscription_plans;

-- 4. 插入新的套餐数据
INSERT INTO subscription_plans (plan_code, name, price, duration_days, description, features, is_active) VALUES
(
    'basic_yearly',
    '基础档',
    139900,  -- ¥1399
    365,
    '年付会员 - 查看所有预测和数据分析',
    '{
        "max_predictions_per_day": 100,
        "access_all_leagues": true,
        "historical_data": true,
        "basic_stats": true,
        "email_alerts": false,
        "ai_chat": false,
        "advanced_filters": false,
        "export_data": false,
        "api_access": false,
        "priority_support": false,
        "custom_alerts": false,
        "portfolio_tracking": false,
        "advanced_analytics": false
    }'::jsonb,
    true
),
(
    'premium_yearly',
    '高级档',
    239900,  -- ¥2399
    365,
    '年付高级会员 - 包含基础档所有功能，额外享有：AI 对话助手、高级筛选、数据导出、投注组合跟踪、高级分析报告、API 访问和优先客服支持',
    '{
        "max_predictions_per_day": -1,
        "access_all_leagues": true,
        "historical_data": true,
        "basic_stats": true,
        "email_alerts": true,
        "ai_chat": true,
        "advanced_filters": true,
        "export_data": true,
        "api_access": true,
        "priority_support": true,
        "custom_alerts": true,
        "portfolio_tracking": true,
        "advanced_analytics": true
    }'::jsonb,
    true
);

-- 5. 创建用户功能权限检查函数
CREATE OR REPLACE FUNCTION check_user_feature(p_user_id INTEGER, p_feature VARCHAR(50))
RETURNS BOOLEAN AS $$
DECLARE
    v_has_feature BOOLEAN := false;
    v_plan_features JSONB;
BEGIN
    -- 检查用户是否有有效订阅
    SELECT sp.features INTO v_plan_features
    FROM users u
    JOIN subscriptions s ON s.user_id = u.id
    JOIN subscription_plans sp ON sp.plan_code = s.plan_code
    WHERE u.id = p_user_id
      AND s.status = 'active'
      AND s.end_date > NOW()
    ORDER BY s.end_date DESC
    LIMIT 1;

    -- 如果找到订阅，检查功能
    IF v_plan_features IS NOT NULL THEN
        v_has_feature := COALESCE((v_plan_features->p_feature)::boolean, false);
    END IF;

    RETURN v_has_feature;
END;
$$ LANGUAGE plpgsql;

-- 6. 创建获取用户套餐信息的函数
CREATE OR REPLACE FUNCTION get_user_plan_info(p_user_id INTEGER)
RETURNS TABLE(
    plan_name VARCHAR(50),
    plan_code VARCHAR(20),
    features JSONB,
    expires_at TIMESTAMP,
    is_trial BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sp.name,
        sp.plan_code,
        sp.features,
        s.end_date,
        false as is_trial
    FROM users u
    JOIN subscriptions s ON s.user_id = u.id
    JOIN subscription_plans sp ON sp.plan_code = s.plan_code
    WHERE u.id = p_user_id
      AND s.status = 'active'
      AND s.end_date > NOW()
    ORDER BY s.end_date DESC
    LIMIT 1;

    -- 如果没有付费订阅，检查试用期
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT
            '试用期'::VARCHAR(50),
            'trial'::VARCHAR(20),
            '{
                "max_predictions_per_day": 10,
                "access_all_leagues": false,
                "historical_data": false,
                "basic_stats": true,
                "email_alerts": false,
                "ai_chat": false,
                "advanced_filters": false,
                "export_data": false,
                "api_access": false,
                "priority_support": false,
                "custom_alerts": false,
                "portfolio_tracking": false,
                "advanced_analytics": false
            }'::JSONB,
            u.trial_end,
            true as is_trial
        FROM users u
        WHERE u.id = p_user_id
          AND u.trial_end > NOW();
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 7. 创建索引
CREATE INDEX IF NOT EXISTS idx_subscription_plans_features ON subscription_plans USING gin(features);
