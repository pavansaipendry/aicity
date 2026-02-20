-- Migration 007: Villains (Phase 4 — Stage 4)
--
-- Adds:
--   gangs table          — named criminal groups with members, formed through recruitment
--   bribe_susceptibility — hidden float on agents (police only). Never shown in dashboard.
--
-- Design rules:
--   - A gang starts PRIVATE. Nobody knows until someone talks or gets arrested.
--   - bribe_susceptibility is set once at police agent creation. Never displayed.
--   - Gangs can be destroyed if the leader is convicted (status → broken).

CREATE TABLE IF NOT EXISTS gangs (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    leader_name         VARCHAR(100) NOT NULL,
    members             TEXT[]  DEFAULT '{}',   -- includes leader
    day_formed          INTEGER NOT NULL,
    status              VARCHAR(20) DEFAULT 'active',   -- active / broken / disbanded
    total_crimes        INTEGER DEFAULT 0,
    known_to_police     BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gangs_status      ON gangs(status);
CREATE INDEX IF NOT EXISTS idx_gangs_leader      ON gangs(leader_name);

ALTER TABLE gangs
    DROP CONSTRAINT IF EXISTS chk_gang_status;
ALTER TABLE gangs
    ADD CONSTRAINT chk_gang_status
    CHECK (status IN ('active', 'broken', 'disbanded'));

-- Hidden corruption attribute on agents.
-- Only meaningful for police. Set at birth, never updated by normal gameplay.
-- Range 0.0 (incorruptible) to 1.0 (actively solicits bribes).
ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS bribe_susceptibility FLOAT DEFAULT 0.0;
