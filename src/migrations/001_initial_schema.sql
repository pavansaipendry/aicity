-- Run this once against your PostgreSQL database:
-- psql -U postgres -d aicity -f migrations/001_initial_schema.sql
-- 001_intital_schema.sql

CREATE TABLE IF NOT EXISTS agents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    role        TEXT NOT NULL,
    tokens      INTEGER NOT NULL DEFAULT 1000,
    age_days    INTEGER NOT NULL DEFAULT 0,
    alive       BOOLEAN NOT NULL DEFAULT TRUE,
    cause_of_death TEXT,
    died_on_day INTEGER,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_snapshots (
    id          SERIAL PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    day         INTEGER NOT NULL,
    tokens      INTEGER NOT NULL,
    earnings    INTEGER,
    events      JSONB,
    snapshot_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id          SERIAL PRIMARY KEY,
    day         INTEGER NOT NULL,
    from_agent  TEXT NOT NULL,
    to_agent    TEXT NOT NULL,
    body        TEXT NOT NULL,
    anonymous   BOOLEAN DEFAULT FALSE,
    sent_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS newspapers (
    id          SERIAL PRIMARY KEY,
    day         INTEGER NOT NULL UNIQUE,
    headline    TEXT,
    body        TEXT,
    written_by  TEXT,
    written_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crimes (
    id          SERIAL PRIMARY KEY,
    day         INTEGER NOT NULL,
    criminal    TEXT NOT NULL,
    victim      TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    verdict     TEXT,
    fine_paid   INTEGER DEFAULT 0,
    exile_days  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS city_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);