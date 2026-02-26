"""
Construction project manager — Phase 6 visual building system.

Any builder agent can propose a project. Multiple agents can be assigned.
Each builder contributes 1 builder-day per day they work on it.
Stage advances when enough builder-days accumulate.

Stage flow (5 stages, matching frontend construction_N tile types):
  0 = planned   (nothing shown)
  1 = surveying (construction_1 tile — stakes in ground)
  2 = foundation(construction_2 — concrete slab)
  3 = framing   (construction_3 — skeleton frame)
  4 = finishing (construction_4 — walls, no roof)
  5 = complete  (final building tile placed via tile_placed event)

Speed formula: days_per_stage = ceil(base_days / sqrt(num_builders))
"""

import math
import json
import os
import random
import psycopg2
import psycopg2.extras
from loguru import logger

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/aicity")


def _conn():
    """Open a psycopg2 connection. Caller is responsible for commit/close."""
    return psycopg2.connect(DATABASE_URL)


# ── Days needed per stage, per project type ──────────────────────────────────
BASE_DAYS_PER_STAGE: dict[str, int] = {
    "house":          2,
    "market":         3,
    "school":         5,
    "hospital":       5,
    "police_station": 4,
    "warehouse":      3,
    "park":           1,
    "bridge":         4,
    "road":           1,
}
DEFAULT_BASE_DAYS = 3

# ── Final tile placed when construction completes ────────────────────────────
BUILDING_TILE_MAP: dict[str, str] = {
    "house":          "house_small",
    "market":         "market",
    "school":         "school",
    "hospital":       "hospital",
    "police_station": "police_station",
    "warehouse":      "warehouse",
    "park":           "tree_oak",
    "bridge":         "road_ew",
    "road":           "road_ns",
}

# ── Stage number → status string ─────────────────────────────────────────────
STAGE_STATUS: dict[int, str] = {
    0: "planned",
    1: "surveying",
    2: "foundation",
    3: "framing",
    4: "finishing",
    5: "complete",
}

# ── Project type → tile footprint (width, height) ────────────────────────────
FOOTPRINT: dict[str, tuple[int, int]] = {
    "house":          (1, 1),
    "market":         (2, 2),
    "school":         (2, 3),
    "hospital":       (2, 3),
    "police_station": (2, 2),
    "warehouse":      (2, 2),
    "park":           (1, 1),
    "bridge":         (1, 1),
    "road":           (1, 1),
}

# ── Column names (shared by all SELECT queries) ───────────────────────────────
_COLS = [
    "id", "name", "project_type", "status", "stage", "total_stages",
    "progress_pct",
    "target_col", "target_row", "width_tiles", "height_tiles", "tile_type",
    "proposed_by", "builders", "builder_days", "days_required",
    "created_day", "completed_day",
]
_SELECT = """
    SELECT id, name, project_type, status, stage, total_stages,
           progress_pct,
           target_col, target_row, width_tiles, height_tiles, tile_type,
           proposed_by, builders, builder_days, days_required,
           created_day, completed_day
    FROM construction_projects
"""


def _row_to_dict(row) -> dict:
    d = dict(zip(_COLS, row))
    if isinstance(d["builders"], str):
        d["builders"] = json.loads(d["builders"])
    return d


# ── Public API ────────────────────────────────────────────────────────────────

def propose_project(
    name: str,
    project_type: str,
    target_col: int,
    target_row: int,
    proposed_by: str,
    day: int,
) -> dict:
    """
    Create a new construction project in 'planned' status.
    Returns the full project dict.
    """
    base = BASE_DAYS_PER_STAGE.get(project_type, DEFAULT_BASE_DAYS)
    total_days = base * 5
    tile_type = BUILDING_TILE_MAP.get(project_type, "warehouse")
    w, h = FOOTPRINT.get(project_type, (2, 2))

    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO construction_projects
              (name, project_type, status, stage, progress_pct,
               target_col, target_row, width_tiles, height_tiles, tile_type,
               proposed_by, builders, builder_days, days_required, created_day)
            VALUES (%s,%s,'planned',0,0,%s,%s,%s,%s,%s,%s,'[]',0,%s,%s)
            RETURNING id
            """,
            (name, project_type, target_col, target_row, w, h, tile_type,
             proposed_by, total_days, day),
        )
        pid = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    logger.info(
        f"[construction] new project #{pid}: '{name}' ({project_type}) "
        f"at ({target_col},{target_row}) proposed by {proposed_by}"
    )
    return get_project(pid)


def assign_builder(project_id: int, builder_name: str) -> None:
    """
    Add a builder to the project's builders list (idempotent).
    Transitions status from 'planned' → 'surveying' on first assignment.
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE construction_projects
            SET builders = (
                SELECT jsonb_agg(DISTINCT elem)
                FROM jsonb_array_elements(builders || %s::jsonb) AS elem
            ),
            status = CASE
                WHEN status = 'planned' THEN 'surveying'
                ELSE status
            END,
            stage = CASE
                WHEN stage = 0 THEN 1
                ELSE stage
            END
            WHERE id = %s
            """,
            (json.dumps([builder_name]), project_id),
        )
        conn.commit()
    finally:
        conn.close()


def advance_project(project_id: int, day: int) -> dict:
    """
    Called once per day for each active project.
    Increments builder_days by num_builders. Advances stage when enough
    builder-days have accumulated.
    Returns the updated project dict.
    """
    project = get_project(project_id)
    if not project or project["status"] == "complete":
        return project  # type: ignore[return-value]

    num_builders = max(1, len(project["builders"]))
    base = BASE_DAYS_PER_STAGE.get(project["project_type"], DEFAULT_BASE_DAYS)
    days_per_stage = max(1, math.ceil(base / math.sqrt(num_builders)))

    new_builder_days = project["builder_days"] + num_builders
    current_stage = project["stage"]

    # Stage advances once per `days_per_stage` builder-days
    completed_stages = min(new_builder_days // days_per_stage, 5)
    new_stage = max(current_stage, completed_stages)

    new_status = STAGE_STATUS.get(new_stage, "complete")
    pct = round((new_stage / 5) * 100, 1)
    completed_day_val = day if new_status == "complete" else None

    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE construction_projects
            SET builder_days   = %s,
                stage          = %s,
                status         = %s,
                progress_pct   = %s,
                completed_day  = COALESCE(completed_day, %s)
            WHERE id = %s
            """,
            (new_builder_days, new_stage, new_status, pct,
             completed_day_val, project_id),
        )
        conn.commit()
    finally:
        conn.close()

    return get_project(project_id)


def get_project(project_id: int) -> dict | None:
    """Return a single project by id, or None if not found."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(_SELECT + "WHERE id = %s", (project_id,))
        row = cur.fetchone()
    finally:
        conn.close()

    return _row_to_dict(row) if row else None


def get_all_active_projects() -> list[dict]:
    """Return all projects that are not yet complete, ordered by creation day."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            _SELECT + "WHERE status != 'complete' ORDER BY created_day, id"
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [_row_to_dict(r) for r in rows]


def pick_build_location(project_type: str,
                        builder_x: float, builder_y: float) -> tuple[int, int]:
    """
    Choose a tile location near the builder for a new project.
    Maps Phase-5 position (0–96, 0–72) → iso grid (0–63) with a small jitter.
    """
    col = round(builder_x * 63 / 96)
    row = round(builder_y * 63 / 72)
    col = max(2, min(61, col + random.randint(-3, 3)))
    row = max(2, min(61, row + random.randint(-3, 3)))
    return col, row
