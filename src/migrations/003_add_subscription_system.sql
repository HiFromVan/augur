-- 订阅系统数据库迁移

-- 1. 修改 users 表，添加订阅相关字段
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR(20) DEFAULT 'trial';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_end TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_end TIMESTAMP;

-- 2. 创建订阅套餐表
CREATE TABLE IF NOT EXISTS subscription_plans (
    id SERIAL PRIMARY KEY,
    plan_code VARCHAR(20) UNIQUE NOT NULL,  -- 'monthly', 'quarterly', 'yearly'
    name VARCHAR(50) NOT NULL,              -- '月付', '季付', '年付'
    price INTEGER NOT NULL,                 -- 价格（分）
    duration_days INTEGER NOT NULL,         -- 有效期（天）
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. 创建订阅记录表
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    plan_code VARCHAR(20) NOT NULL,
    amount INTEGER NOT NULL,                -- 实际支付金额（分）
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'active',    -- 'active', 'expired', 'cancelled'
    payment_method VARCHAR(20),             -- 'alipay', 'wechat', 'manual'
    payment_id VARCHAR(100),                -- 支付平台订单号
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 4. 插入默认套餐数据
INSERT INTO subscription_plans (plan_code, name, price, duration_days, description) VALUES
    ('monthly', '月付', 19900, 30, '每月199元，随时取消'),
    ('quarterly', '季付', 56800, 90, '每季568元，平均189元/月'),
    ('yearly', '年付', 219900, 365, '每年2199元，平均183元/月')
ON CONFLICT (plan_code) DO NOTHING;

-- 5. 为现有用户设置试用期（3个月）
UPDATE users
SET trial_end = NOW() + INTERVAL '3 months',
    subscription_tier = 'trial'
WHERE trial_end IS NULL;

-- 6. 创建索引
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_users_subscription_end ON users(subscription_end);
CREATE INDEX IF NOT EXISTS idx_users_trial_end ON users(trial_end);

-- 7. 创建函数：检查用户是否有有效订阅
CREATE OR REPLACE FUNCTION check_user_subscription(p_user_id INTEGER)
RETURNS TABLE(
    has_access BOOLEAN,
    subscription_type VARCHAR(20),
    expires_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE
            WHEN u.subscription_end > NOW() THEN true
            WHEN u.trial_end > NOW() THEN true
            ELSE false
        END as has_access,
        CASE
            WHEN u.subscription_end > NOW() THEN 'paid'
            WHEN u.trial_end > NOW() THEN 'trial'
            ELSE 'expired'
        END as subscription_type,
        CASE
            WHEN u.subscription_end > NOW() THEN u.subscription_end
            WHEN u.trial_end > NOW() THEN u.trial_end
            ELSE NULL
        END as expires_at
    FROM users u
    WHERE u.id = p_user_id;
END;
$$ LANGUAGE plpgsql;
