-- Migration 003: Messenger story tiers
-- Run: psql -d aicity -f 003_stories.sql

CREATE TABLE IF NOT EXISTS stories (
    id          SERIAL PRIMARY KEY,
    type        TEXT NOT NULL,  -- 'daily' | 'weekly' | 'monthly'
    day         INTEGER NOT NULL,
    week        INTEGER,        -- which week (1-4), NULL for daily
    title       TEXT,
    body        TEXT NOT NULL,
    written_by  TEXT NOT NULL,
    written_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stories_type ON stories(type);
CREATE INDEX IF NOT EXISTS idx_stories_day  ON stories(day);