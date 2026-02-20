-- Migration 006: Police Cases (Phase 4 — Stage 3: Police Complaint Book)
--
-- Every formal complaint filed with police creates a case record here.
-- The police officer investigates daily, writing case notes to this table.
-- Cases go cold after 14 days without new evidence.
-- When a case closes (solved or cold), police writes a full narrative report.
--
-- Case flow:
--   event_log (REPORTED) → police_cases (open)
--   → daily investigation notes added
--   → arrest requested → court verdict → case closed (solved)
--   OR → 14 days no leads → case closed (cold)
--   → cold case can be reopened if new evidence surfaces

CREATE TABLE IF NOT EXISTS police_cases (
    id              SERIAL PRIMARY KEY,
    event_log_id    INTEGER REFERENCES event_log(id),  -- the triggering REPORTED event
    day_opened      INTEGER NOT NULL,
    complaint_text  TEXT,                              -- what was reported
    complainant     VARCHAR(100),                      -- who filed the report (victim/witness)
    suspect_names   TEXT[] DEFAULT '{}',               -- agents currently suspected
    evidence_refs   JSONB DEFAULT '[]',                -- refs to event_log entries and token records
    case_notes      JSONB DEFAULT '[]',                -- [{day, note, suspect, confidence}] daily entries
    status          VARCHAR(20) DEFAULT 'open',        -- open / solved / cold
    resolution      TEXT,                              -- brief outcome summary
    police_report   TEXT,                              -- full LLM-written narrative on close
    day_closed      INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_police_cases_status     ON police_cases(status);
CREATE INDEX IF NOT EXISTS idx_police_cases_day_opened ON police_cases(day_opened);

ALTER TABLE police_cases
    DROP CONSTRAINT IF EXISTS chk_case_status;
ALTER TABLE police_cases
    ADD CONSTRAINT chk_case_status
    CHECK (status IN ('open', 'solved', 'cold'));
