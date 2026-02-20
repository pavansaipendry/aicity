-- Migration 009: Phase 5 — Agent positions, meeting events, criminal alliances
-- Run: psql -d aicity -f src/migrations/009_phase5_positions.sql

ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS x FLOAT DEFAULT 0.0,
  ADD COLUMN IF NOT EXISTS y FLOAT DEFAULT 0.0,
  ADD COLUMN IF NOT EXISTS home_tile_x INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS home_tile_y INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS home_claimed BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS city_map_state (
  id SERIAL PRIMARY KEY,
  day INT NOT NULL,
  time_phase VARCHAR(16) NOT NULL,  -- dawn/morning/afternoon/evening/night
  standing_assets JSONB DEFAULT '[]',
  claimed_homes JSONB DEFAULT '[]',
  recorded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS meeting_events (
  id SERIAL PRIMARY KEY,
  day INT NOT NULL,
  participants TEXT[] NOT NULL,     -- agent names
  location VARCHAR(64) NOT NULL,    -- LOC_* constant
  outcome VARCHAR(256),             -- what happened mechanically
  recorded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS criminal_alliances (
  id SERIAL PRIMARY KEY,
  initiator_name TEXT NOT NULL,
  partner_name TEXT NOT NULL,
  day_formed INT NOT NULL,
  alliance_type VARCHAR(64),        -- 'gang_blackmail', 'dual_theft', etc.
  status VARCHAR(32) DEFAULT 'active',
  total_operations INT DEFAULT 0,
  known_to_police BOOLEAN DEFAULT FALSE
);
