-- 添加 AI 预测说明和媒体分析字段

-- 1. 在 matches 表添加 AI 相关字段
ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS ai_explanation TEXT,
    ADD COLUMN IF NOT EXISTS ai_explanation_generated_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS media_analysis JSONB,
    ADD COLUMN IF NOT EXISTS media_analysis_generated_at TIMESTAMP;

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS idx_matches_ai_explanation ON matches(id) WHERE ai_explanation IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_matches_media_analysis ON matches(id) WHERE media_analysis IS NOT NULL;

-- 3. 添加注释
COMMENT ON COLUMN matches.ai_explanation IS 'AI 生成的预测说明';
COMMENT ON COLUMN matches.ai_explanation_generated_at IS 'AI 说明生成时间';
COMMENT ON COLUMN matches.media_analysis IS '媒体舆情分析（JSON格式）';
COMMENT ON COLUMN matches.media_analysis_generated_at IS '媒体分析生成时间';
