-- Migration 004: Event Log (Phase 4 — Stage 1: Information Asymmetry)
--
-- Every significant action in the city is logged here with a visibility state.
-- Events start PRIVATE (only the actor knows) and can be promoted
-- as witnesses emerge, rumors spread, and reports are filed.
--
-- Visibility states:
--   PRIVATE   → Only the actor knows. No evidence visible to others.
--   WITNESSED → 1+ agents were nearby. They have a vague Qdrant memory of something.
--   RUMOR     → Witnessed agents gossiped via messaging. May be distorted.
--   REPORTED  → Formally filed with police. Now in the complaint system.
--   PUBLIC    → Court verdict issued, OR 5+ agents know independently.
--               Only PUBLIC events can appear in the newspaper.

CREATE TABLE IF NOT EXISTS event_log (
    id               SERIAL PRIMARY KEY,
    day              INTEGER NOT NULL,
    event_type       VARCHAR(50) NOT NULL,   -- 'theft', 'arrest', 'arson', 'assault', 'bribe', 'blackmail', 'death', 'birth'
    actor_name       VARCHAR(100),           -- who did it
    target_name      VARCHAR(100),           -- who it happened to (may be NULL)
    asset_id         INTEGER,               -- city asset involved (NULL if none)
    description      TEXT NOT NULL,         -- plain text description of what happened
    visibility       VARCHAR(20) NOT NULL DEFAULT 'PRIVATE',
    witnesses        TEXT[] DEFAULT '{}',   -- agent names who witnessed it
    evidence_trail   JSONB DEFAULT '{}',    -- token ledger refs, witness notes, physical clues
    created_at       TIMESTAMP DEFAULT NOW()
);

-- Indexes for the queries police and the newspaper will run
CREATE INDEX IF NOT EXISTS idx_event_log_day        ON event_log(day);
CREATE INDEX IF NOT EXISTS idx_event_log_visibility ON event_log(visibility);
CREATE INDEX IF NOT EXISTS idx_event_log_actor      ON event_log(actor_name);
CREATE INDEX IF NOT EXISTS idx_event_log_target     ON event_log(target_name);
CREATE INDEX IF NOT EXISTS idx_event_log_type       ON event_log(event_type);

-- Constraint: visibility must be a known state
ALTER TABLE event_log
    DROP CONSTRAINT IF EXISTS chk_visibility;
ALTER TABLE event_log
    ADD CONSTRAINT chk_visibility
    CHECK (visibility IN ('PRIVATE', 'WITNESSED', 'RUMOR', 'REPORTED', 'PUBLIC'));
