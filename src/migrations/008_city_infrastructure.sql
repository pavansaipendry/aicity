-- Stage 5: City Infrastructure
-- city_assets: persistent things the city builds
-- shared_projects: in-progress collaborative builds

CREATE TABLE IF NOT EXISTS city_assets (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    asset_type          VARCHAR(50),
    builders            TEXT[]           DEFAULT '{}',
    day_built           INTEGER          NOT NULL,
    status              VARCHAR(20)      DEFAULT 'standing',   -- standing / damaged / destroyed
    benefit_description TEXT,
    benefit_value       JSONB            DEFAULT '{}',
    day_destroyed       INTEGER,
    created_at          TIMESTAMP        DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shared_projects (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    project_type    VARCHAR(50),
    creator_id      VARCHAR(100),
    goal_days       INTEGER NOT NULL,
    contributors    JSONB            DEFAULT '{}',   -- {agent_name: last_contribution_day}
    progress        FLOAT            DEFAULT 0,      -- float: 0.5 increments allowed
    status          VARCHAR(20)      DEFAULT 'active',  -- active / completed / abandoned
    day_started     INTEGER          NOT NULL,
    day_completed   INTEGER,
    created_at      TIMESTAMP        DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_city_assets_status    ON city_assets(status);
CREATE INDEX IF NOT EXISTS idx_city_assets_type      ON city_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_shared_projects_status ON shared_projects(status);
