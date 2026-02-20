-- 009_world_tiles.sql
-- Stores every non-grass tile in the city grid.
-- Grass is the default — we only persist tiles that differ from grass.
-- Grid is 64×64 tiles for Phase 6 Sprint 1 (scales to 128×128 with culling in Sprint 6).
--
-- layer values:
--   0 = ground (water, dirt, sand — replaces grass)
--   1 = path/road (drawn on top of ground)
--   2 = nature (trees, rocks, bushes — drawn on top of roads)
--   3 = building (structures — drawn on top of everything)

CREATE TABLE IF NOT EXISTS world_tiles (
    id         SERIAL PRIMARY KEY,
    col        INTEGER NOT NULL,
    row        INTEGER NOT NULL,
    tile_type  VARCHAR(64) NOT NULL,
    layer      INTEGER NOT NULL DEFAULT 0,
    built_by   VARCHAR(128),   -- which agent placed this tile (NULL = world-generated)
    built_day  INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (col, row, layer)    -- one tile per (col, row, layer) combination
);

-- Fast lookups by position (used every time a client connects or a tile changes)
CREATE INDEX IF NOT EXISTS idx_world_tiles_pos ON world_tiles (col, row);
CREATE INDEX IF NOT EXISTS idx_world_tiles_layer ON world_tiles (layer);
