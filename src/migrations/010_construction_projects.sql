-- src/migrations/010_construction_projects.sql
-- Tracks every construction project from planning to completion.
-- Multi-agent coordination: multiple builders can contribute builder-days.
--
-- Stage flow: 0=planned → 1=surveying → 2=foundation → 3=framing → 4=finishing → 5=complete
-- Speed formula: days_per_stage = ceil(base_days / sqrt(num_builders))

CREATE TABLE IF NOT EXISTS construction_projects (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(256) NOT NULL,
    -- e.g. "Market Stall", "Bridge over river", "South Road Extension"
    project_type    VARCHAR(64) NOT NULL,
    -- e.g. "market", "house", "school", "hospital", "police_station", "warehouse", "park"
    status          VARCHAR(32) NOT NULL DEFAULT 'planned',
    -- planned → surveying → foundation → framing → finishing → complete
    stage           INTEGER NOT NULL DEFAULT 0,
    -- 0=planned, 1=surveying(stakes), 2=foundation, 3=framing, 4=finishing, 5=complete
    total_stages    INTEGER NOT NULL DEFAULT 5,
    progress_pct    FLOAT NOT NULL DEFAULT 0.0,
    -- 0.0 to 100.0

    -- Location on the tile grid (top-left corner of footprint)
    target_col      INTEGER NOT NULL,
    target_row      INTEGER NOT NULL,
    width_tiles     INTEGER NOT NULL DEFAULT 2,
    height_tiles    INTEGER NOT NULL DEFAULT 2,

    -- Final tile type to place on completion
    tile_type       VARCHAR(64) NOT NULL DEFAULT 'market',

    -- Coordination
    proposed_by     VARCHAR(128) NOT NULL,
    builders        JSONB NOT NULL DEFAULT '[]',
    -- e.g. ["Kai Fox", "Atlas Grey"]
    builder_days    INTEGER NOT NULL DEFAULT 0,
    days_required   INTEGER NOT NULL DEFAULT 5,
    -- total builder-days needed (base_days * total_stages)

    created_day     INTEGER,
    completed_day   INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_construction_status   ON construction_projects (status);
CREATE INDEX IF NOT EXISTS idx_construction_location ON construction_projects (target_col, target_row);
