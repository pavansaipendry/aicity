-- Migration 002: Newborn comprehension system
-- Run: psql -U postgres -d aicity -f migrations/002_newborn_comprehension.sql

ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS comprehension_score INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS assigned_teacher    TEXT;

-- Track graduation events
CREATE TABLE IF NOT EXISTS graduations (
    id              SERIAL PRIMARY KEY,
    agent_name      TEXT NOT NULL,
    graduated_on_day INTEGER NOT NULL,
    chosen_role     TEXT NOT NULL,
    teacher_name    TEXT,
    final_comprehension INTEGER,
    graduation_statement TEXT,
    graduated_at    TIMESTAMPTZ DEFAULT NOW()
);