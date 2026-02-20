"""
Asset System — Phase 4, Stage 5

Manages city_assets table: creation, daily benefit application, destruction.

Standing assets provide daily token benefits to relevant role-holders.
Saboteurs can destroy them (logged PRIVATE with evidence trail).

Asset benefits (applied once per day before agent turns):
  watchtower    → Police +30/day. Thief detection +20% (mechanical bonus in city_v3).
  hospital      → Healer +40/day from the facility.
  market_stall  → Merchants split 50 tokens/day passive income.
  school        → Teacher +30/day. Newborns comprehension growth x2 (applied in behaviors.py).
  road          → Explorer +25/day.
  archive       → Flag only — used by newspaper to write richer chronicles.

Sabotage evidence trail (from doc spec):
  "scorch marks found on the foundation"
  "tools found nearby — not belonging to any builder"
  "footprints in the dirt, leading away from the east side"
  etc.
"""

import os
import json
import random

import psycopg2
import psycopg2.extras
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/aicity"
)

# Themed names — generated when the asset is first built
ASSET_NAMES: dict[str, list[str]] = {
    "watchtower":   ["Northern Watchtower", "East Watchtower", "The Sentinel Tower", "Ashwatch Tower"],
    "hospital":     ["City Hospital", "The Healing Hall", "St. Marcus Infirmary", "The Menders' House"],
    "market_stall": ["East Market", "The Common Exchange", "Voss Market", "The Trade Post"],
    "school":       ["School of Arts", "The Learning Hall", "Keeper's Academy", "The Open School"],
    "road":         ["The North Road", "River Path", "The Old Track", "Founders' Road"],
    "archive":      ["The City Archive", "The Memory Hall", "Keeper's Archive", "The Record House"],
}

# Evidence trail flavor text (doc spec: leaves physical clues for police to find)
SABOTAGE_EVIDENCE: list[str] = [
    "scorch marks found on the foundation",
    "tools found nearby — not belonging to any known builder",
    "footprints in the dirt, leading away from the east side",
    "a faint smell of accelerant near the wreckage",
    "a bent crowbar found wedged deep in the structure",
    "a torn piece of cloth caught on the outer wall",
    "chisel marks inconsistent with construction work",
]


class AssetSystem:
    """
    Manages city_assets: creation, daily benefit application, destruction.
    """

    def __init__(self, event_log=None):
        self.event_log = event_log

    # ─── Creation ─────────────────────────────────────────────────────────────

    def create_asset(
        self,
        project_type: str,
        builders: list[str],
        day: int,
        benefit_description: str,
        benefit_value: dict,
    ) -> int:
        """
        Called by ProjectSystem._complete_project when a project finishes.
        Creates the city_assets entry. Returns asset_id or -1 on failure.
        """
        name_options = ASSET_NAMES.get(project_type, [f"{project_type.replace('_', ' ').title()}"])
        name = random.choice(name_options)

        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO city_assets
                        (name, asset_type, builders, day_built, benefit_description, benefit_value)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        name,
                        project_type,
                        builders,
                        day,
                        benefit_description,
                        json.dumps(benefit_value),
                    ),
                )
                asset_id = cur.fetchone()[0]

            logger.info(
                f"AssetSystem: '{name}' ({project_type}) built on Day {day} "
                f"by {builders}. Asset #{asset_id}."
            )
            return asset_id

        except Exception as e:
            logger.warning(f"AssetSystem.create_asset failed: {e}")
            return -1

    # ─── Daily benefit application ────────────────────────────────────────────

    def apply_daily_benefits(
        self,
        all_agents,        # list of Agent objects (mutated directly)
        token_engine,
        day: int,
    ) -> list[dict]:
        """
        Called once per day BEFORE agent turns so benefits are active today.
        Iterates standing assets and applies token bonuses to relevant agents.
        Returns list of benefit events for broadcast/logging.
        """
        assets = self.get_standing_assets()
        if not assets:
            return []

        events = []
        for asset in assets:
            asset_type = asset["asset_type"]
            benefit = asset.get("benefit_value") or {}

            if asset_type == "watchtower":
                police_bonus = int(benefit.get("police_bonus", 30))
                for a in all_agents:
                    if getattr(a, "role", "") == "police" and a.status == "alive":
                        token_engine.earn(a.id, police_bonus, "watchtower_patrol_bonus")
                        a.tokens = token_engine.get_balance(a.id)
                        events.append({
                            "type": "asset_benefit",
                            "asset": asset["name"],
                            "agent": a.name,
                            "tokens": police_bonus,
                            "detail": "watchtower patrol bonus",
                        })

            elif asset_type == "hospital":
                healer_bonus = int(benefit.get("healer_bonus", 40))
                for a in all_agents:
                    if getattr(a, "role", "") == "healer" and a.status == "alive":
                        token_engine.earn(a.id, healer_bonus, "hospital_facility_bonus")
                        a.tokens = token_engine.get_balance(a.id)
                        events.append({
                            "type": "asset_benefit",
                            "asset": asset["name"],
                            "agent": a.name,
                            "tokens": healer_bonus,
                            "detail": "hospital facility bonus",
                        })

            elif asset_type == "market_stall":
                passive = int(benefit.get("passive_income", 50))
                merchants = [
                    a for a in all_agents
                    if getattr(a, "role", "") == "merchant" and a.status == "alive"
                ]
                if merchants:
                    per_merchant = max(1, passive // len(merchants))
                    for a in merchants:
                        token_engine.earn(a.id, per_merchant, "market_stall_passive_income")
                        a.tokens = token_engine.get_balance(a.id)
                        events.append({
                            "type": "asset_benefit",
                            "asset": asset["name"],
                            "agent": a.name,
                            "tokens": per_merchant,
                            "detail": "market stall passive income",
                        })

            elif asset_type == "school":
                teacher_bonus = int(benefit.get("teacher_bonus", 30))
                for a in all_agents:
                    if getattr(a, "role", "") == "teacher" and a.status == "alive":
                        token_engine.earn(a.id, teacher_bonus, "school_facility_bonus")
                        a.tokens = token_engine.get_balance(a.id)
                        events.append({
                            "type": "asset_benefit",
                            "asset": asset["name"],
                            "agent": a.name,
                            "tokens": teacher_bonus,
                            "detail": "school facility bonus",
                        })

            elif asset_type == "road":
                explorer_bonus = int(benefit.get("explorer_bonus", 25))
                for a in all_agents:
                    if getattr(a, "role", "") == "explorer" and a.status == "alive":
                        token_engine.earn(a.id, explorer_bonus, "road_exploration_bonus")
                        a.tokens = token_engine.get_balance(a.id)
                        events.append({
                            "type": "asset_benefit",
                            "asset": asset["name"],
                            "agent": a.name,
                            "tokens": explorer_bonus,
                            "detail": "road exploration bonus",
                        })

            # archive: flag only (no daily token benefit)

        if events:
            logger.debug(f"AssetSystem: applied {len(events)} benefit(s) on Day {day}")

        return events

    def get_asset_flags(self) -> dict[str, bool]:
        """
        Returns a dict of active asset type flags.
        e.g. {"watchtower": True, "school": True, "archive": True}
        Used to apply behavioral multipliers (detection bonus, graduation speed, etc.)
        """
        return {a["asset_type"]: True for a in self.get_standing_assets()}

    # ─── Destruction ──────────────────────────────────────────────────────────

    def destroy_asset(
        self,
        asset_id: int,
        saboteur_name: str,
        day: int,
    ):
        """
        Saboteur destroys a city asset.
        Status → 'destroyed'. Logs as PRIVATE with physical evidence trail.
        Another agent at location gets a WITNESSED memory fragment via event_log.
        """
        asset = self._get_asset_by_id(asset_id)
        if not asset or asset["status"] == "destroyed":
            return

        evidence = random.choice(SABOTAGE_EVIDENCE)

        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE city_assets
                    SET status = 'destroyed', day_destroyed = %s
                    WHERE id = %s
                    """,
                    (day, asset_id),
                )

            if self.event_log:
                self.event_log.log_event(
                    day=day,
                    event_type="sabotage",
                    actor_name=saboteur_name,
                    asset_id=asset_id,
                    description=(
                        f"{asset['name']} was destroyed. "
                        f"Evidence at the scene: {evidence}. "
                        f"It will take days to rebuild."
                    ),
                    initial_visibility="PRIVATE",
                )

            logger.warning(
                f"AssetSystem: '{asset['name']}' DESTROYED by {saboteur_name} "
                f"on Day {day}. Evidence: {evidence}"
            )

        except Exception as e:
            logger.warning(f"AssetSystem.destroy_asset failed: {e}")

    def damage_asset(self, asset_id: int, day: int):
        """Partially damage an asset — it still works but may be repaired."""
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE city_assets SET status = 'damaged' WHERE id = %s AND status = 'standing'",
                    (asset_id,),
                )
        except Exception as e:
            logger.warning(f"AssetSystem.damage_asset failed: {e}")

    # ─── Queries ──────────────────────────────────────────────────────────────

    def get_standing_assets(self) -> list[dict]:
        """Returns all standing (or damaged — still active) assets."""
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    """
                    SELECT id, name, asset_type, builders, day_built,
                           status, benefit_description, benefit_value
                    FROM city_assets
                    WHERE status IN ('standing', 'damaged')
                    ORDER BY day_built ASC
                    """
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"AssetSystem.get_standing_assets failed: {e}")
            return []

    def get_all_assets(self) -> list[dict]:
        """All assets including destroyed ones — for dashboard/archive view."""
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT * FROM city_assets ORDER BY day_built ASC")
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"AssetSystem.get_all_assets failed: {e}")
            return []

    def _get_asset_by_id(self, asset_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    "SELECT id, name, asset_type, status FROM city_assets WHERE id = %s",
                    (asset_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"AssetSystem._get_asset_by_id failed: {e}")
            return None

    def _connect(self):
        return psycopg2.connect(DATABASE_URL)
