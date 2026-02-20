-- Migration 005: Mood Score (Phase 4 — Stage 2: Behavioral Drift)
--
-- Every agent has a mood_score that tracks their emotional state over time.
-- Range: -1.0 (rock bottom) to +1.0 (thriving).
--
-- This is SEPARATE from the LLM's self-reported "mood" word.
-- mood_score is system-managed: updated by what actually happens to the agent.
-- It feeds back into LLM decisions as rich descriptive context.
--
-- Update triggers (examples):
--   Stolen from:             -0.20
--   Daily survival stress:   -0.10 (when tokens < 200)
--   Justice served:          +0.20
--   Healer helped them:      +0.15
--   Earned well today:       +0.05
--   Ally sent support:       +0.10
--
-- At mood_score < -0.70: agent is susceptible to gang recruitment messages.
-- At mood_score < -0.90: agent may take desperate or extreme actions.

ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS mood_score FLOAT DEFAULT 0.0;

-- Clamp check — enforced in Python, but good to document the range here.
-- ALTER TABLE agents ADD CONSTRAINT chk_mood_score CHECK (mood_score BETWEEN -1.0 AND 1.0);
