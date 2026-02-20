"""
Event Log — Phase 4, Stage 1: Information Asymmetry

Every significant action in AIcity is recorded here with a visibility state.
This is the foundation for realistic police investigations, rumor spreading,
and a newspaper that only knows what's publicly confirmed.

Visibility state machine:
    PRIVATE   → Only the actor knows. Leaves no visible evidence.
    WITNESSED → 1+ agents were nearby. They have a vague memory of something.
    RUMOR     → A witness told someone. May be distorted. Not confirmed.
    REPORTED  → Formally filed with police. Opens a case.
    PUBLIC    → Court verdict, or 5+ agents independently know. Newspaper can report.

Key rule: the Messenger/Newspaper LLM only ever sees PUBLIC events.
          Police only sees REPORTED, PUBLIC, and WITNESSED events — not PRIVATE.
          Each agent only knows what they personally witnessed or were told.
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

# Witness chance per agent per crime event.
# 15% means each bystander has a 15% chance of having been nearby.
# Crimes at busy locations (market, common areas) should use a higher value.
_DEFAULT_WITNESS_CHANCE = 0.15
_BUSY_LOCATION_WITNESS_CHANCE = 0.30

# Vague witness memory templates — witnesses see fragments, not full truth.
# Keys match event_type values logged in behaviors.py
_WITNESS_TEMPLATES: dict[str, list[str]] = {
    "theft": [
        "I noticed {actor} acting suspiciously near {target}'s area. Something felt off.",
        "I saw someone moving quickly away from where {target} usually is. Couldn't make out who.",
        "There was a commotion near {target}'s area. I didn't see exactly what happened.",
        "I caught a glimpse of someone rushing away around the time {target} reported being robbed.",
        "I saw {actor} watching {target} from a distance earlier. Didn't think much of it at the time.",
    ],
    "arson": [
        "I saw smoke rising from that direction. Not sure what caused it.",
        "I noticed someone near the area earlier that night. Couldn't see their face clearly.",
        "I smelled smoke and saw a figure leaving quickly. Couldn't identify them.",
        "Something was burning. I saw a shadow moving away from it fast.",
        "I heard something crack and saw flames. By the time I got close, whoever did it was gone.",
    ],
    "assault": [
        "I heard raised voices near {target}'s area but didn't want to get involved.",
        "I saw two people arguing intensely. One of them might have been {target}.",
        "I noticed {target} looked shaken afterward but I don't know why.",
        "There was a scuffle. I only caught the tail end of it.",
    ],
    "bribe": [
        "I saw {actor} meeting with someone privately. They exchanged something — I couldn't tell what.",
        "There was a quiet conversation that stopped when I walked past. Something felt wrong about it.",
        "I saw tokens change hands between {actor} and someone I couldn't identify clearly.",
    ],
    "blackmail": [
        "I overheard part of a conversation that sounded threatening. Someone was being pressured.",
        "I saw a message being passed. The recipient looked pale afterward.",
        "I heard {actor} talking in low tones. The other person looked scared.",
    ],
}

_FALLBACK_WITNESS_TEMPLATES = [
    "Something happened near {actor}'s area. I'm not sure what.",
    "I noticed unusual activity but couldn't make sense of it.",
    "There was something going on. I only caught a glimpse.",
]


class EventLog:
    """
    The city's hidden ledger. Logs every significant action with
    the visibility level appropriate to how secret it was.

    Pass in memory_system as a dict {agent_name: AgentMemory} so that
    when witnesses are detected, their Qdrant memories get the fragment.
    """

    def __init__(self, memory_system: dict = None):
        # Dict of {agent_name: AgentMemory instance}
        self._memories: dict = memory_system or {}

    def set_memories(self, memory_system: dict):
        """Update the memory system reference (e.g. after new agents are born)."""
        self._memories = memory_system

    # ─── Core logging ─────────────────────────────────────────────────────────

    def log_event(
        self,
        day: int,
        event_type: str,
        actor_name: str,
        description: str,
        target_name: str = None,
        asset_id: int = None,
        initial_visibility: str = "PRIVATE",
    ) -> int:
        """
        Record a new event. Returns the event_id (used for witness detection
        and evidence references). Returns -1 if DB write fails.

        Most crimes should start PRIVATE.
        Public events (births, deaths, graduations) should use PUBLIC.
        Arrests should use REPORTED (they're public acts).
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO event_log
                        (day, event_type, actor_name, target_name,
                         asset_id, description, visibility)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (day, event_type, actor_name, target_name,
                     asset_id, description, initial_visibility),
                )
                event_id = cur.fetchone()[0]
                logger.debug(
                    f"EventLog #{event_id}: {event_type} by {actor_name} "
                    f"→ target={target_name} [{initial_visibility}]"
                )
                return event_id
        except Exception as e:
            logger.warning(f"EventLog.log_event failed: {e}")
            return -1

    # ─── Witness detection ────────────────────────────────────────────────────

    def detect_witnesses(
        self,
        event_id: int,
        all_agents: list[dict],
        actor_name: str,
        target_name: str = None,
        witness_chance: float = _DEFAULT_WITNESS_CHANCE,
    ):
        """
        After a crime, roll each alive bystander for witness probability.
        If they witnessed it: promotes event to WITNESSED, stores a vague
        fragment in their Qdrant memory.

        Call this from city_v3.py after execute_action() returns,
        passing all_agent_dicts and the event_id from the result.
        """
        if event_id < 0:
            return

        witnesses_found = []
        for agent in all_agents:
            name = agent.get("name")
            # Actor and target cannot be neutral witnesses of their own event
            if name in (actor_name, target_name):
                continue
            if agent.get("status") != "alive":
                continue
            if random.random() < witness_chance:
                witnesses_found.append(name)

        if witnesses_found:
            self._promote_to_witnessed(event_id, witnesses_found)

    def _promote_to_witnessed(self, event_id: int, witness_names: list[str]):
        """
        Update event visibility to WITNESSED, store witness list,
        and write a vague memory fragment into each witness's Qdrant collection.
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                # Fetch the event so we can generate appropriate memory text
                cur.execute("SELECT * FROM event_log WHERE id = %s", (event_id,))
                row = cur.fetchone()
                if not row:
                    return
                event = dict(row)

                # Only promote upward — never downgrade visibility
                cur.execute(
                    """
                    UPDATE event_log
                    SET visibility = 'WITNESSED',
                        witnesses  = %s
                    WHERE id = %s
                      AND visibility = 'PRIVATE'
                    """,
                    (witness_names, event_id),
                )

            # Store vague memory fragments in each witness's Qdrant memory
            templates = _WITNESS_TEMPLATES.get(
                event["event_type"], _FALLBACK_WITNESS_TEMPLATES
            )
            actor = event.get("actor_name") or "someone"
            target = event.get("target_name") or "someone"

            for witness_name in witness_names:
                memory = self._memories.get(witness_name)
                if not memory:
                    continue
                template = random.choice(templates)
                fragment = template.format(actor=actor, target=target)
                try:
                    memory.remember(
                        f"Day {event['day']}: {fragment}",
                        memory_type="observation",
                        day=event["day"],
                    )
                    logger.debug(
                        f"EventLog: {witness_name} got witness fragment for event #{event_id}"
                    )
                except Exception as e:
                    logger.debug(
                        f"EventLog: could not store witness memory for {witness_name}: {e}"
                    )

        except Exception as e:
            logger.warning(f"EventLog._promote_to_witnessed failed: {e}")

    # ─── Reporting ────────────────────────────────────────────────────────────

    def file_report(
        self,
        event_id: int,
        reporting_agent: str,
        day: int,
    ) -> bool:
        """
        An agent formally reports an event to police.
        Promotes the event to REPORTED — the police complaint system picks it up.
        Returns True on success.
        """
        if event_id < 0:
            return False
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE event_log
                    SET visibility    = 'REPORTED',
                        evidence_trail = evidence_trail || %s::jsonb
                    WHERE id = %s
                    """,
                    (
                        json.dumps({
                            "reported_by": reporting_agent,
                            "reported_on_day": day,
                        }),
                        event_id,
                    ),
                )
            logger.info(
                f"EventLog: {reporting_agent} filed report on event #{event_id} → REPORTED"
            )
            return True
        except Exception as e:
            logger.warning(f"EventLog.file_report failed: {e}")
            return False

    def make_public(self, event_id: int, reason: str = "court_verdict"):
        """
        Mark an event as PUBLIC.
        Called after a court verdict, or when 5+ agents independently know about it.
        From this point the Messenger/Newspaper can reference it.
        """
        if event_id < 0:
            return
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE event_log
                    SET visibility     = 'PUBLIC',
                        evidence_trail = evidence_trail || %s::jsonb
                    WHERE id = %s
                    """,
                    (json.dumps({"made_public_reason": reason}), event_id),
                )
            logger.info(f"EventLog: event #{event_id} → PUBLIC ({reason})")
        except Exception as e:
            logger.warning(f"EventLog.make_public failed: {e}")

    def spread_rumor(
        self,
        event_id: int,
        from_agent: str,
        to_agent: str,
        day: int,
    ):
        """
        A witness gossips about what they saw — promotes event to RUMOR.
        The actual message is sent via the existing Redis messaging system.
        This call just updates the event_log visibility so police can track
        how the information is spreading.
        """
        if event_id < 0:
            return
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE event_log
                    SET visibility = CASE
                            WHEN visibility IN ('PRIVATE', 'WITNESSED') THEN 'RUMOR'
                            ELSE visibility
                        END,
                        evidence_trail = evidence_trail || %s::jsonb
                    WHERE id = %s
                    """,
                    (
                        json.dumps({
                            "rumor_from": from_agent,
                            "rumor_to": to_agent,
                            "on_day": day,
                        }),
                        event_id,
                    ),
                )
        except Exception as e:
            logger.warning(f"EventLog.spread_rumor failed: {e}")

    # ─── Query: Police ────────────────────────────────────────────────────────

    def get_evidence_for_police(
        self,
        suspect_name: str = None,
        target_name: str = None,
        event_type: str = None,
        since_day: int = 0,
    ) -> list[dict]:
        """
        Returns evidence that police can legally access:
          - REPORTED and PUBLIC events (always visible to police)
          - WITNESSED events (partial — police knows someone saw something)

        Police CANNOT see PRIVATE or RUMOR events directly.
        They can only work with what was witnessed or reported.
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                conditions = [
                    "day >= %s",
                    "visibility IN ('REPORTED', 'PUBLIC', 'WITNESSED')",
                ]
                params: list = [since_day]

                if suspect_name:
                    conditions.append("(actor_name = %s OR target_name = %s)")
                    params.extend([suspect_name, suspect_name])
                if target_name:
                    conditions.append("target_name = %s")
                    params.append(target_name)
                if event_type:
                    conditions.append("event_type = %s")
                    params.append(event_type)

                cur.execute(
                    f"""
                    SELECT id, day, event_type, actor_name, target_name,
                           description, visibility, witnesses, evidence_trail
                    FROM event_log
                    WHERE {" AND ".join(conditions)}
                    ORDER BY day DESC
                    LIMIT 30
                    """,
                    params,
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"EventLog.get_evidence_for_police failed: {e}")
            return []

    def get_all_open_cases_evidence(self, since_day: int = 0) -> list[dict]:
        """
        Returns all REPORTED events since a given day.
        Used by the police complaint system to find new cases to open.
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    """
                    SELECT id, day, event_type, actor_name, target_name,
                           description, witnesses, evidence_trail
                    FROM event_log
                    WHERE visibility = 'REPORTED' AND day >= %s
                    ORDER BY day ASC
                    """,
                    (since_day,),
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"EventLog.get_all_open_cases_evidence failed: {e}")
            return []

    # ─── Query: Newspaper ─────────────────────────────────────────────────────

    def get_public_events(self, since_day: int = 0) -> list[dict]:
        """
        Returns only PUBLIC events — the only thing the Messenger can see.
        The newspaper is always behind the truth.
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    """
                    SELECT id, day, event_type, actor_name, target_name, description
                    FROM event_log
                    WHERE visibility = 'PUBLIC' AND day >= %s
                    ORDER BY day DESC
                    LIMIT 30
                    """,
                    (since_day,),
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"EventLog.get_public_events failed: {e}")
            return []

    # ─── Query: Agent personal view ───────────────────────────────────────────

    def get_events_known_to_agent(
        self, agent_name: str, since_day: int = 0
    ) -> list[dict]:
        """
        What a specific agent can know:
          - Events where they are the actor or target
          - Events where they appear in the witnesses list
          - All REPORTED and PUBLIC events (these are city-wide knowledge)

        This is what gets injected into an agent's brain context for decision-making.
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    """
                    SELECT id, day, event_type, actor_name, target_name,
                           description, visibility
                    FROM event_log
                    WHERE day >= %s AND (
                        actor_name = %s
                        OR target_name = %s
                        OR %s = ANY(witnesses)
                        OR visibility IN ('REPORTED', 'PUBLIC')
                    )
                    ORDER BY day DESC
                    LIMIT 20
                    """,
                    (since_day, agent_name, agent_name, agent_name),
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"EventLog.get_events_known_to_agent failed: {e}")
            return []

    # ─── Victim self-discovery ────────────────────────────────────────────────

    def victim_discovers_crime(
        self,
        target_name: str,
        event_type: str,
        day: int,
    ) -> list[dict]:
        """
        Called when a victim checks their token balance and notices something
        is wrong. Returns PRIVATE crimes against them they may now want to report.

        The victim doesn't know WHO did it — just that something happened.
        This is how theft victims eventually file police reports.
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    """
                    SELECT id, day, event_type, actor_name, target_name, description
                    FROM event_log
                    WHERE target_name = %s
                      AND event_type = %s
                      AND visibility IN ('PRIVATE', 'WITNESSED', 'RUMOR')
                      AND day >= %s
                    ORDER BY day DESC
                    LIMIT 5
                    """,
                    (target_name, event_type, day - 3),
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"EventLog.victim_discovers_crime failed: {e}")
            return []

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _connect(self):
        return psycopg2.connect(DATABASE_URL)
