"""
src/world/tile_manager.py

Single source of truth for all tile reads and writes.
Every agent action, construction step, and world-gen call goes through here.

Grid: 64×64 (col 0–63, row 0–63). Grass is the implicit default — we only
store tiles that differ from grass. That keeps the table small and fast.

Layer values (same as migration 009):
  0 = ground  (water, dirt, sand)
  1 = road    (drawn above ground)
  2 = nature  (trees, rocks, bushes)
  3 = building
"""

import math
import random
import os
import psycopg2
import psycopg2.extras
from loguru import logger

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/aicity")

GRID_SIZE = 64  # 64×64 tile grid


# ── DB helper ──────────────────────────────────────────────────────────────────

def _conn():
    """Open a psycopg2 connection.  Caller is responsible for commit/close."""
    return psycopg2.connect(DATABASE_URL)


# ── Read ───────────────────────────────────────────────────────────────────────

def get_world_state() -> list[dict]:
    """
    Return every non-grass tile as a list of dicts.
    Called once when a browser client connects, and after bulk world-gen.

    Why only non-grass? Grass is the default — sending 4,096 identical tiles
    on every page load would be wasteful. The frontend draws grass everywhere
    and then paints the exceptions on top.
    """
    conn = _conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT col, row, tile_type, layer, built_by, built_day "
            "FROM world_tiles ORDER BY layer, (col + row)"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ── Write ──────────────────────────────────────────────────────────────────────

def place_tile(
    col: int,
    row: int,
    tile_type: str,
    layer: int = 0,
    built_by: str | None = None,
    built_day: int | None = None,
) -> dict:
    """
    Upsert a single tile.  Returns the final tile dict.

    Why UPSERT? Each (col, row, layer) can only have one tile — if builders
    lay a road and later decide to upgrade it, we overwrite in place rather
    than stacking duplicate rows.
    """
    conn = _conn()
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            INSERT INTO world_tiles (col, row, tile_type, layer, built_by, built_day)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (col, row, layer) DO UPDATE
                SET tile_type  = EXCLUDED.tile_type,
                    built_by   = EXCLUDED.built_by,
                    built_day  = EXCLUDED.built_day,
                    updated_at = NOW()
            RETURNING col, row, tile_type, layer, built_by, built_day
            """,
            (col, row, tile_type, layer, built_by, built_day),
        )
        row_data = dict(cur.fetchone())
        conn.commit()
        return row_data
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def remove_tile(col: int, row: int, layer: int) -> bool:
    """Delete a tile (returns it to default grass). Returns True if deleted."""
    conn = _conn()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM world_tiles WHERE col=%s AND row=%s AND layer=%s",
            (col, row, layer),
        )
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── World generation ───────────────────────────────────────────────────────────

def generate_initial_world(day: int = 1) -> int:
    """
    Seed the world on Day 1.  Idempotent — safe to call multiple times;
    it skips generation if any tiles already exist.

    What gets generated:
    ┌──────────────────────────────────────────────────────────┐
    │  River  — a winding strip of water tiles (layer 0)       │
    │           runs north-to-south, wobbles ±4 cols via sin() │
    │  Trees  — scattered randomly (layer 2), ~18% density     │
    │           avoided inside the river and its 2-col buffer  │
    └──────────────────────────────────────────────────────────┘

    Returns the number of tiles inserted.

    Why sin() for the river? A perfectly straight river looks fake.
    sin(row * frequency) * amplitude gives a smooth, natural-looking
    meander without needing a noise library.
    """
    conn = _conn()
    try:
        conn.autocommit = False
        cur = conn.cursor()

        # ── Guard: skip if world already has tiles ─────────────────────────
        cur.execute("SELECT COUNT(*) FROM world_tiles")
        if cur.fetchone()[0] > 0:
            logger.info("🌍 World already generated — skipping")
            conn.rollback()
            return 0

        tiles: list[tuple] = []

        # ── River (layer 0 = ground, tile_type = 'water') ─────────────────
        river_center = GRID_SIZE // 2  # start at col 32
        for row in range(GRID_SIZE):
            # Smooth meander: amplitude 4, period ~20 rows
            wobble = int(math.sin(row * 0.31) * 4)
            river_col = river_center + wobble
            # River is 2 tiles wide for visual weight
            for dc in (0, 1):
                c = river_col + dc
                if 0 <= c < GRID_SIZE:
                    tiles.append((c, row, "water", 0, None, day))

        # Build a quick set of water positions for tree-placement guard
        water_positions = {(t[0], t[1]) for t in tiles}

        # ── Trees (layer 2 = nature) ────────────────────────────────────────
        rng = random.Random(42)  # fixed seed → reproducible map
        tree_types = ["tree_pine", "tree_oak", "bush", "rock"]
        tree_weights = [0.45, 0.35, 0.12, 0.08]

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                # Skip water tiles and their 2-tile buffer zone
                if any((col + dc, row) in water_positions for dc in (-2, -1, 0, 1, 2)):
                    continue
                if rng.random() < 0.18:
                    ttype = rng.choices(tree_types, weights=tree_weights)[0]
                    tiles.append((col, row, ttype, 2, None, day))

        # ── Bulk insert ────────────────────────────────────────────────────
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO world_tiles (col, row, tile_type, layer, built_by, built_day) "
            "VALUES %s ON CONFLICT (col, row, layer) DO NOTHING",
            tiles,
        )
        conn.commit()
        logger.info(f"🌍 World generated — {len(tiles)} tiles placed (Day {day})")
        return len(tiles)

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
