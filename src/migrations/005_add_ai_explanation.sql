-- Add AI-generated explanation field to matches table
ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS ai_explanation TEXT,
    ADD COLUMN IF NOT EXISTS explanation_generated_at TIMESTAMP;

-- Add index for faster queries
CREATE INDEX IF NOT EXISTS idx_matches_explanation_generated
    ON matches(explanation_generated_at)
    WHERE ai_explanation IS NOT NULL;
