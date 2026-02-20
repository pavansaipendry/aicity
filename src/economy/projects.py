"""
Project System — Phase 4, Stage 5

Handles collaborative building projects between agents.
When multiple agents work together, they create city assets that provide
lasting daily benefits to the whole city.

Joint action rules (Phase4_planofAction.md):
  - Agent A starts project → shared_projects entry, invite messages to required co-builders
  - Agent B joins next day (or same day if message processed first)
  - Both contribute that day → +1.0 progress
  - Only 1 contributor that day → +0.5 progress (partial credit)
  - On completion → city_assets entry created, logged as PUBLIC
  - No contributions for 3 days → status = 'abandoned'

Asset specs (what each project type requires and provides):
  watchtower    2 builders          4 days  Police +30/day, thief detection +20%
  hospital      2 builders + healer 5 days  Healer x2, sick agents recover faster
  market_stall  merchant + builder  3 days  Passive 50/day, trade bonus +15%
  school        teacher + 2 builders 4 days Newborns 2x faster, teacher +30/day
  road          explorer + builder  2 days  Explorer +25/day
  archive       messenger + teacher 3 days  Chronicle enriched (flag)
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

# ─── Asset specifications ─────────────────────────────────────────────────────
# Single source of truth for what each project type requires and provides.

ASSET_SPECS: dict[str, dict] = {
    "watchtower": {
        "display_name": "Watchtower",
        "required_roles": {"builder": 2},
        "goal_days": 4,
        "benefit_description": "Police earn +30/day on patrol. Thief detection +20%.",
        "benefit_value": {"police_bonus": 30, "thief_detection_bonus": 0.20},
    },
    "hospital": {
        "display_name": "Hospital",
        "required_roles": {"builder": 2, "healer": 1},
        "goal_days": 5,
        "benefit_description": "Healer effectiveness x2. Sick agents recover faster.",
        "benefit_value": {"healer_bonus": 40, "heart_attack_resistance": 0.50},
    },
    "market_stall": {
        "display_name": "Market Stall",
        "required_roles": {"merchant": 1, "builder": 1},
        "goal_days": 3,
        "benefit_description": "Passive income 50 tokens/day. Agents trade at a bonus.",
        "benefit_value": {"passive_income": 50, "trade_bonus": 0.15},
    },
    "school": {
        "display_name": "School",
        "required_roles": {"teacher": 1, "builder": 2},
        "goal_days": 4,
        "benefit_description": "Newborns graduate 2x faster. Teacher earns +30/day.",
        "benefit_value": {"newborn_speed_multiplier": 2.0, "teacher_bonus": 30},
    },
    "road": {
        "display_name": "Road",
        "required_roles": {"explorer": 1, "builder": 1},
        "goal_days": 2,
        "benefit_description": "Explorer discovers areas faster. New locations unlocked.",
        "benefit_value": {"explorer_bonus": 25},
    },
    "archive": {
        "display_name": "Archive",
        "required_roles": {"messenger": 1, "teacher": 1},
        "goal_days": 3,
        "benefit_description": "Monthly chronicle richer. More structured city history.",
        "benefit_value": {"chronicle_enhanced": True},
    },
}

# Days of no contributions before project is automatically abandoned
ABANDON_DAYS = 3

# Build priority: easiest / most impactful first
BUILD_PRIORITY = ["road", "market_stall", "watchtower", "school", "archive", "hospital"]


class ProjectSystem:
    """
    Manages shared_projects table: creation, joining, contributions, completion.
    Called from city_v3.py each day.
    """

    def __init__(self, event_log=None):
        self.event_log = event_log

    # ─── Starting projects ────────────────────────────────────────────────────

    def start_project(
        self,
        creator_name: str,
        creator_role: str,
        project_type: str,
        day: int,
        all_agents: list[dict],
    ) -> int:
        """
        Creates a new shared_projects entry and sends invite messages to
        all required co-contributors.
        Returns project_id on success, -1 on failure or if already exists.
        """
        spec = ASSET_SPECS.get(project_type)
        if not spec:
            return -1

        # Don't build something that already exists or is in-progress
        if self._asset_or_project_exists(project_type):
            logger.debug(
                f"ProjectSystem: '{project_type}' already exists or in progress."
            )
            return -1

        contributors = {creator_name: 0}  # {name: last_contribution_day}; 0 = not yet contributed
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO shared_projects
                        (name, project_type, creator_id, goal_days, contributors, day_started)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        spec["display_name"],
                        project_type,
                        creator_name,
                        spec["goal_days"],
                        json.dumps(contributors),
                        day,
                    ),
                )
                project_id = cur.fetchone()[0]

            logger.info(
                f"ProjectSystem: {creator_name} started '{spec['display_name']}' "
                f"(id={project_id}, goal={spec['goal_days']} days)"
            )
            self._send_invites(
                project_id=project_id,
                project_name=spec["display_name"],
                creator_name=creator_name,
                creator_role=creator_role,
                spec=spec,
                all_agents=all_agents,
                day=day,
            )
            return project_id

        except Exception as e:
            logger.warning(f"ProjectSystem.start_project failed: {e}")
            return -1

    def _send_invites(
        self,
        project_id: int,
        project_name: str,
        creator_name: str,
        creator_role: str,
        spec: dict,
        all_agents: list[dict],
        day: int,
    ):
        """Send Redis invite messages to required co-contributors."""
        from src.agents.messaging import send_message

        required = dict(spec["required_roles"])
        invited: set[str] = set()

        for role, count_needed in required.items():
            # Creator fills one slot for their own role
            slots_to_fill = count_needed - (1 if role == creator_role else 0)
            candidates = [
                a for a in all_agents
                if a.get("role") == role
                and a.get("status") == "alive"
                and a["name"] != creator_name
                and a["name"] not in invited
            ]
            for candidate in candidates[:slots_to_fill]:
                send_message(
                    from_name=creator_name,
                    from_role=creator_role,
                    to_name=candidate["name"],
                    content=(
                        f"I'm starting a {project_name} for the city. "
                        f"I need your help — your role makes this possible. "
                        f"If you're willing to work with me, just say so in your next action. "
                        f"Once it's done, the whole city benefits."
                    ),
                    day=day,
                )
                invited.add(candidate["name"])

    # ─── Joining projects ─────────────────────────────────────────────────────

    def join_project(
        self,
        agent_name: str,
        agent_role: str,
        day: int,
        all_agents: list[dict],
    ) -> int:
        """
        Joins an active project that needs this role.
        Returns project_id if joined, -1 if nothing to join.
        """
        try:
            active = self._get_active_projects()
            for project in active:
                contributors = project["contributors"] or {}
                if agent_name in contributors:
                    continue  # already part of this one

                spec = ASSET_SPECS.get(project["project_type"], {})
                needed = spec.get("required_roles", {}).get(agent_role, 0)
                # Count how many current contributors have this role
                current_count = sum(
                    1 for name in contributors
                    if any(
                        a.get("role") == agent_role and a["name"] == name
                        for a in all_agents
                    )
                )
                if current_count < needed:
                    contributors[agent_name] = 0
                    with self._connect() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE shared_projects SET contributors = %s WHERE id = %s",
                            (json.dumps(contributors), project["id"]),
                        )
                    logger.info(
                        f"ProjectSystem: {agent_name} joined '{project['name']}' "
                        f"(project #{project['id']})"
                    )
                    return project["id"]

            return -1

        except Exception as e:
            logger.warning(f"ProjectSystem.join_project failed: {e}")
            return -1

    # ─── Daily contribution ───────────────────────────────────────────────────

    def contribute(self, agent_name: str, day: int) -> int:
        """
        Records that agent_name contributed to their project today.
        Stores the current day as the value for this contributor.
        Returns project_id, or -1 if not in any active project.
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    """
                    SELECT id, contributors
                    FROM shared_projects
                    WHERE status = 'active'
                      AND contributors ? %s
                    LIMIT 1
                    """,
                    (agent_name,),
                )
                row = cur.fetchone()
                if not row:
                    return -1

                project_id = row["id"]
                contributors = dict(row["contributors"])
                contributors[agent_name] = day  # mark as contributed today

                cur2 = conn.cursor()
                cur2.execute(
                    "UPDATE shared_projects SET contributors = %s WHERE id = %s",
                    (json.dumps(contributors), project_id),
                )

            return project_id

        except Exception as e:
            logger.warning(f"ProjectSystem.contribute failed: {e}")
            return -1

    # ─── Daily update loop ────────────────────────────────────────────────────

    def update_daily(
        self,
        day: int,
        all_agents: list[dict],
        asset_system,
    ) -> list[dict]:
        """
        Called once per day AFTER all agents have acted.
        - Calculates today's progress for each active project
        - Completes projects that hit their goal
        - Abandons projects with no activity for 3+ days
        Returns list of events (completion, abandonment) for broadcasting.
        """
        events = []
        try:
            for project in self._get_active_projects():
                event = self._step_project(project, day, all_agents, asset_system)
                if event:
                    events.append(event)
        except Exception as e:
            logger.warning(f"ProjectSystem.update_daily failed: {e}")
        return events

    def _step_project(
        self,
        project: dict,
        day: int,
        all_agents: list[dict],
        asset_system,
    ) -> dict | None:
        """
        Advance one project by one day.
        Returns an event dict if something notable happened (completion/abandonment).
        """
        project_id = project["id"]
        contributors = project["contributors"] or {}
        goal_days = project["goal_days"]
        current_progress = project["progress"]
        day_started = project["day_started"]

        spec = ASSET_SPECS.get(project["project_type"], {})
        required_count = sum(spec.get("required_roles", {}).values())

        # Count how many contributors marked today's day
        active_today = sum(1 for d in contributors.values() if d == day)

        if active_today >= required_count:
            progress_gain = 1.0
        elif active_today >= 1:
            progress_gain = 0.5
        else:
            progress_gain = 0.0

        new_progress = current_progress + progress_gain

        # Abandonment: no activity for ABANDON_DAYS past the start
        days_elapsed = day - day_started
        if progress_gain == 0.0 and days_elapsed >= ABANDON_DAYS:
            self._abandon_project(project_id)
            logger.info(
                f"ProjectSystem: '{project['name']}' abandoned on Day {day} "
                f"(no contributions for {days_elapsed} days)"
            )
            return {
                "type": "project_abandoned",
                "project_name": project["name"],
                "project_type": project["project_type"],
                "day": day,
            }

        # Write updated progress
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE shared_projects SET progress = %s WHERE id = %s",
                    (new_progress, project_id),
                )
        except Exception as e:
            logger.warning(f"ProjectSystem: progress write failed: {e}")

        # Completion check
        if new_progress >= goal_days:
            return self._complete_project(project, day, asset_system)

        return None

    def _complete_project(
        self,
        project: dict,
        day: int,
        asset_system,
    ) -> dict:
        """Mark project completed and create the city_asset."""
        project_id = project["id"]
        project_type = project["project_type"]
        spec = ASSET_SPECS.get(project_type, {})
        builder_names = list((project["contributors"] or {}).keys())

        asset_id = asset_system.create_asset(
            project_type=project_type,
            builders=builder_names,
            day=day,
            benefit_description=spec.get("benefit_description", ""),
            benefit_value=spec.get("benefit_value", {}),
        )

        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE shared_projects
                    SET status = 'completed', day_completed = %s, progress = goal_days
                    WHERE id = %s
                    """,
                    (day, project_id),
                )
        except Exception as e:
            logger.warning(f"ProjectSystem._complete_project status update failed: {e}")

        if self.event_log:
            self.event_log.log_event(
                day=day,
                event_type="asset_built",
                actor_name=", ".join(builder_names),
                description=(
                    f"A new {spec.get('display_name', project_type)} has been completed "
                    f"by {', '.join(builder_names)}. "
                    f"{spec.get('benefit_description', '')}"
                ),
                initial_visibility="PUBLIC",
            )

        logger.info(
            f"ProjectSystem: '{project['name']}' COMPLETED on Day {day}. "
            f"Asset #{asset_id} created."
        )
        return {
            "type": "project_completed",
            "project_name": project["name"],
            "project_type": project_type,
            "asset_id": asset_id,
            "builders": builder_names,
            "benefit": spec.get("benefit_description", ""),
            "day": day,
        }

    # ─── Queries ──────────────────────────────────────────────────────────────

    def get_project_for_agent(self, agent_name: str) -> dict | None:
        """Returns the active project an agent is currently part of, or None."""
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    """
                    SELECT id, name, project_type, contributors, goal_days, progress
                    FROM shared_projects
                    WHERE status = 'active' AND contributors ? %s
                    LIMIT 1
                    """,
                    (agent_name,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"ProjectSystem.get_project_for_agent failed: {e}")
            return None

    def best_startable_project(
        self, creator_role: str, alive_role_counts: dict
    ) -> str | None:
        """
        Returns the best project_type the city can currently build,
        prioritising easier / more impactful projects first.
        Returns None if nothing is feasible.
        """
        for project_type in BUILD_PRIORITY:
            spec = ASSET_SPECS[project_type]
            required = spec["required_roles"]
            if all(
                alive_role_counts.get(role, 0) >= count
                for role, count in required.items()
            ) and not self._asset_or_project_exists(project_type):
                return project_type
        return None

    def _get_active_projects(self) -> list[dict]:
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    """
                    SELECT id, name, project_type, creator_id, goal_days,
                           contributors, progress, day_started
                    FROM shared_projects
                    WHERE status = 'active'
                    ORDER BY day_started ASC
                    """
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"ProjectSystem._get_active_projects failed: {e}")
            return []

    def _asset_or_project_exists(self, project_type: str) -> bool:
        """True if this asset type is already standing or actively being built."""
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT 1 FROM city_assets WHERE asset_type = %s AND status = 'standing' LIMIT 1",
                    (project_type,),
                )
                if cur.fetchone():
                    return True
                cur.execute(
                    "SELECT 1 FROM shared_projects WHERE project_type = %s AND status = 'active' LIMIT 1",
                    (project_type,),
                )
                return cur.fetchone() is not None
        except Exception as e:
            logger.warning(f"ProjectSystem._asset_or_project_exists failed: {e}")
            return False

    def _abandon_project(self, project_id: int):
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE shared_projects SET status = 'abandoned' WHERE id = %s",
                    (project_id,),
                )
        except Exception as e:
            logger.warning(f"ProjectSystem._abandon_project failed: {e}")

    def _connect(self):
        return psycopg2.connect(DATABASE_URL)
