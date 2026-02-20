"""
Gang System — Phase 4, Stage 4

Gangs form organically when a thief (or ambitious criminal) has been
operating long enough and vulnerable agents exist to recruit.

Formation is NOT scripted — it depends on:
  - Whether the criminal has built confidence (high earnings, low police heat)
  - Whether vulnerable agents exist (mood_score < -0.50, not police/healer)
  - A daily probability roll

Once formed, a gang:
  - Gets a name and a DB record (status: PRIVATE in event_log)
  - Grants the leader a coordination bonus on theft
  - Can be exposed when a member is arrested (they might talk)
  - Can be broken if the leader is convicted

The gang's existence is never directly told to the newspaper.
It surfaces only through investigation, arrests, and rumors.
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

# Gang names — feel like real criminal organizations, not cartoonish
GANG_NAMES = [
    "The Hollow", "Iron Circle", "The Ashen", "Night Council",
    "The Scorched", "Void Pact", "Grey Wolves", "The Fracture",
    "Black Ledger", "The Quiet Ones",
]

# Chance per day that a qualifying criminal forms a gang (if they sent recruitment messages)
GANG_FORMATION_CHANCE = 0.30

# Member must be below this mood_score to be recruitable — matches doc spec
RECRUIT_MOOD_THRESHOLD = -0.70

# Minimum total members (leader + recruits). Doc says "3+ agents accept" → leader + 2 min.
MIN_GANG_SIZE = 3


class GangSystem:
    """
    Manages gang formation, membership, and coordination bonuses.
    Called once per day from city_v3.py after all agents have acted.
    """

    def __init__(self, event_log):
        self.event_log = event_log

    # ─── Daily check ──────────────────────────────────────────────────────────

    def run_daily(self, all_agents: list[dict], day: int) -> list[dict]:
        """
        Main daily entry point. Checks whether any criminal agent
        qualifies to form a gang. Returns list of formation events
        (for dashboard broadcast).

        Does NOT auto-form gangs every day — GANG_FORMATION_CHANCE applies.
        """
        events = []

        # Only criminals without an existing gang can form one
        criminal_roles = {"thief", "blackmailer", "saboteur", "gang_leader"}
        candidates = [
            a for a in all_agents
            if a.get("role") in criminal_roles
            and a.get("status") == "alive"
            and not self._agent_in_gang(a["name"])
        ]

        for candidate in candidates:
            if random.random() > GANG_FORMATION_CHANCE:
                continue

            # Find recruitable agents
            recruits = [
                a for a in all_agents
                if a.get("status") == "alive"
                and a["name"] != candidate["name"]
                and float(a.get("mood_score", 0.0)) < RECRUIT_MOOD_THRESHOLD
                and a.get("role") not in ["police", "healer", "newborn"]
                and not self._agent_in_gang(a["name"])
            ]

            if len(recruits) < MIN_GANG_SIZE - 1:
                continue  # Not enough vulnerable agents to recruit

            # Pick the most desperate recruits
            recruits_sorted = sorted(
                recruits, key=lambda a: float(a.get("mood_score", 0.0))
            )
            chosen = recruits_sorted[:MIN_GANG_SIZE - 1]
            members = [candidate["name"]] + [r["name"] for r in chosen]

            gang_id = self._form_gang(
                leader_name=candidate["name"],
                members=members,
                day=day,
            )

            if gang_id > 0:
                events.append({
                    "type": "gang_formed",
                    "gang_id": gang_id,
                    "leader": candidate["name"],
                    "members": members,
                    "day": day,
                })
                logger.warning(
                    f"GANG FORMED: {candidate['name']} recruited "
                    f"{[r['name'] for r in chosen]} on Day {day}"
                )

        return events

    # ─── Coordination bonus ───────────────────────────────────────────────────

    def get_gang_bonus(self, agent_name: str) -> float:
        """
        Returns a theft multiplier for gang members.
        Solo thief: 1.0x. Gang leader: 1.4x. Gang member: 1.2x.
        """
        gang = self._get_agent_gang(agent_name)
        if not gang:
            return 1.0
        if gang["leader_name"] == agent_name:
            return 1.4
        return 1.2

    def increment_gang_crimes(self, leader_name: str):
        """Called after a successful gang-coordinated crime."""
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE gangs SET total_crimes = total_crimes + 1
                    WHERE leader_name = %s AND status = 'active'
                """, (leader_name,))
        except Exception as e:
            logger.warning(f"GangSystem.increment_gang_crimes failed: {e}")

    # ─── Exposure ─────────────────────────────────────────────────────────────

    def expose_gang_member(self, arrested_agent: str, day: int) -> str | None:
        """
        When a gang member is arrested, roll for whether they talk.
        If they talk: gang becomes known_to_police.
        Returns the gang name if exposed, None otherwise.
        """
        gang = self._get_agent_gang(arrested_agent)
        if not gang:
            return None

        # 40% chance a arrested member talks
        if random.random() < 0.40:
            try:
                with self._connect() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        UPDATE gangs SET known_to_police = TRUE
                        WHERE id = %s
                    """, (gang["id"],))
                # Log the exposure as a RUMOR — police now has a lead
                self.event_log.log_event(
                    day=day,
                    event_type="gang_exposed",
                    actor_name=arrested_agent,
                    description=(
                        f"{arrested_agent} revealed the existence of {gang['name']} "
                        f"under questioning. Leader: {gang['leader_name']}."
                    ),
                    initial_visibility="RUMOR",
                )
                logger.info(
                    f"GangSystem: {arrested_agent} talked — {gang['name']} exposed to police"
                )
                return gang["name"]
            except Exception as e:
                logger.warning(f"GangSystem.expose_gang_member failed: {e}")

        return None

    def break_gang(self, leader_name: str, day: int):
        """
        Called when the gang leader is convicted.
        Gang status → broken. Members are on their own.
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE gangs SET status = 'broken'
                    WHERE leader_name = %s AND status = 'active'
                """, (leader_name,))
            self.event_log.log_event(
                day=day,
                event_type="gang_broken",
                actor_name=leader_name,
                description=f"The gang led by {leader_name} has collapsed after their conviction.",
                initial_visibility="PUBLIC",
            )
            logger.info(f"GangSystem: Gang led by {leader_name} broken on Day {day}")
        except Exception as e:
            logger.warning(f"GangSystem.break_gang failed: {e}")

    # ─── Queries ──────────────────────────────────────────────────────────────

    def get_active_gangs(self) -> list[dict]:
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT id, name, leader_name, members, day_formed,
                           total_crimes, known_to_police
                    FROM gangs WHERE status = 'active'
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"GangSystem.get_active_gangs failed: {e}")
            return []

    def _agent_in_gang(self, agent_name: str) -> bool:
        gang = self._get_agent_gang(agent_name)
        return gang is not None

    def _get_agent_gang(self, agent_name: str) -> dict | None:
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT id, name, leader_name, members, day_formed, status
                    FROM gangs
                    WHERE %s = ANY(members) AND status = 'active'
                    LIMIT 1
                """, (agent_name,))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"GangSystem._get_agent_gang failed: {e}")
            return None

    def _get_thief_gang(self, leader_name: str) -> dict | None:
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT id, name, leader_name, members
                    FROM gangs
                    WHERE leader_name = %s AND status = 'active'
                    LIMIT 1
                """, (leader_name,))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"GangSystem._get_thief_gang failed: {e}")
            return None

    # ─── Formation ────────────────────────────────────────────────────────────

    def _form_gang(self, leader_name: str, members: list[str], day: int) -> int:
        """
        Create a gang record in DB.
        Returns gang_id or -1 on failure.
        """
        name = random.choice(GANG_NAMES)
        # Make sure the name isn't already taken
        existing = {g["name"] for g in self.get_active_gangs()}
        attempts = 0
        while name in existing and attempts < len(GANG_NAMES):
            name = random.choice(GANG_NAMES)
            attempts += 1

        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO gangs (name, leader_name, members, day_formed)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (name, leader_name, members, day))
                gang_id = cur.fetchone()[0]

            # Log gang formation as PRIVATE — nobody knows yet
            self.event_log.log_event(
                day=day,
                event_type="gang_formed",
                actor_name=leader_name,
                description=(
                    f"{leader_name} formed a criminal group called {name} "
                    f"with {len(members) - 1} recruited member(s)."
                ),
                initial_visibility="PRIVATE",
            )
            return gang_id

        except Exception as e:
            logger.warning(f"GangSystem._form_gang failed: {e}")
            return -1

    def _connect(self):
        return psycopg2.connect(DATABASE_URL)
