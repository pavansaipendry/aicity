"""
MeetingManager — Phase 5
Detects when two agents have expressed meeting intent AND are in the same zone,
then fires a real mechanical outcome and logs a meeting_events DB record.

Meeting intent keywords (checked against both agent's last message):
    "meet", "talk", "discuss", "rendezvous", "come to", "see you", "find me",
    "let's go", "meet me", "join me", "i'll be at", "waiting for"
"""

import random
from typing import Optional

import psycopg2
from loguru import logger

MEETING_INTENT_WORDS = [
    "meet", "talk", "discuss", "rendezvous", "come to", "see you", "find me",
    "let's go", "meet me", "join me", "i'll be at", "waiting for", "cave",
    "whispering", "station", "alley", "square", "market", "together",
    "our arrangement", "finalize", "our deal", "alliance",
]

# Role-pair → handler method name (both orderings must be handled)
MEETING_OUTCOMES: dict[tuple[str, str], str] = {
    ("gang_leader", "blackmailer"): "_form_criminal_alliance",
    ("blackmailer", "gang_leader"): "_form_criminal_alliance",
    ("gang_leader", "thief"):       "_expand_gang",
    ("thief", "gang_leader"):       "_expand_gang",
    ("blackmailer", "explorer"):    "_attempt_compromise",
    ("explorer", "blackmailer"):    "_attempt_compromise",
    ("blackmailer", "thief"):       "_attempt_compromise",
    ("thief", "blackmailer"):       "_attempt_compromise",
    ("police", "explorer"):         "_debrief_informant",
    ("explorer", "police"):         "_debrief_informant",
    ("police", "lawyer"):           "_debrief_informant",
    ("lawyer", "police"):           "_debrief_informant",
    ("builder", "merchant"):        "_start_project",
    ("merchant", "builder"):        "_start_project",
    ("builder", "teacher"):         "_start_project",
    ("teacher", "builder"):         "_start_project",
    ("builder", "explorer"):        "_start_project",
    ("explorer", "builder"):        "_start_project",
    ("merchant", "healer"):         "_trade_goods",
    ("healer", "merchant"):         "_trade_goods",
}


class MeetingManager:
    """
    Phase 5 meeting system.

    Call check_meetings() once per day after all agent turns complete.
    It scans the recent Redis message log (passed in as agent_dicts with
    'last_message' field) and the PositionManager for proximity, then fires
    outcome handlers and writes meeting_events records to Postgres.
    """

    def __init__(self, db_conn) -> None:
        """
        db_conn: psycopg2 connection to the aicity database.
        Pass None to skip DB persistence (for testing).
        """
        self.conn = db_conn
        # Track which pairs already met today to avoid double-firing
        self._met_today: set[frozenset] = set()

    # ── Main entry point ──────────────────────────────────────────────────────

    def check_meetings(
        self,
        day: int,
        all_agents: list[dict],
        position_manager,
    ) -> list[dict]:
        """
        Called once per day after all agent turns.

        all_agents: list of dicts with at minimum:
            {name, role, status, tokens, last_message (str|None), last_action (str|None)}

        Returns a list of meeting event dicts for WebSocket broadcast.
        """
        self._met_today.clear()
        events: list[dict] = []

        alive = [a for a in all_agents if a.get("status") == "alive"]

        for i, agent_a in enumerate(alive):
            for agent_b in alive[i + 1:]:
                pair = frozenset([agent_a["name"], agent_b["name"]])
                if pair in self._met_today:
                    continue

                if not self._has_meeting_intent(agent_a, agent_b):
                    continue

                if not position_manager.agents_at_same_zone(
                    agent_a["name"], agent_b["name"], radius=8.0
                ):
                    continue

                # Determine location
                zone = position_manager.which_zone(agent_a["name"]) or "LOC_TOWN_SQUARE"
                outcome_text, event_extra = self._fire_outcome(
                    agent_a, agent_b, day, zone
                )

                self._met_today.add(pair)
                self._record_meeting(day, [agent_a["name"], agent_b["name"]], zone, outcome_text)

                meeting_event = {
                    "type": "meeting",
                    "day": day,
                    "participants": [agent_a["name"], agent_b["name"]],
                    "location": zone,
                    "outcome": outcome_text,
                    **event_extra,
                }
                events.append(meeting_event)
                logger.info(
                    f"[Meeting] Day {day}: {agent_a['name']} + {agent_b['name']} "
                    f"at {zone} → {outcome_text}"
                )

        return events

    # ── Outcome handlers ──────────────────────────────────────────────────────

    def _fire_outcome(
        self, agent_a: dict, agent_b: dict, day: int, zone: str
    ) -> tuple[str, dict]:
        """Routes to the appropriate outcome handler based on role pair."""
        role_pair = (agent_a["role"], agent_b["role"])
        handler_name = MEETING_OUTCOMES.get(role_pair)

        if handler_name is None:
            # Generic social meeting
            return self._social_meeting(agent_a, agent_b, day)

        handler = getattr(self, handler_name, None)
        if handler is None:
            return f"{agent_a['name']} and {agent_b['name']} met and talked.", {}

        return handler(agent_a, agent_b, day)

    def _form_criminal_alliance(
        self, agent_a: dict, agent_b: dict, day: int
    ) -> tuple[str, dict]:
        """
        Creates a criminal_alliances DB record.
        Fires when gang_leader + blackmailer meet with intent.
        """
        # Determine who is who
        if agent_a["role"] == "gang_leader":
            initiator, partner = agent_a, agent_b
        else:
            initiator, partner = agent_b, agent_a

        alliance_type = "gang_blackmail"
        outcome = (
            f"{initiator['name']} and {partner['name']} have formalized a secret "
            f"criminal alliance. They will coordinate operations together."
        )

        if self.conn:
            try:
                with self.conn.cursor() as cur:
                    # Check if alliance already exists
                    cur.execute(
                        """
                        SELECT id FROM criminal_alliances
                        WHERE initiator_name = %s AND partner_name = %s
                          AND status = 'active'
                        """,
                        (initiator["name"], partner["name"]),
                    )
                    if cur.fetchone() is None:
                        cur.execute(
                            """
                            INSERT INTO criminal_alliances
                              (initiator_name, partner_name, day_formed, alliance_type)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (initiator["name"], partner["name"], day, alliance_type),
                        )
                        self.conn.commit()
                        logger.info(
                            f"[Alliance] {initiator['name']} ↔ {partner['name']} "
                            f"alliance created (day {day})"
                        )
                    else:
                        # Alliance exists — increment operations
                        cur.execute(
                            """
                            UPDATE criminal_alliances
                            SET total_operations = total_operations + 1
                            WHERE initiator_name = %s AND partner_name = %s
                              AND status = 'active'
                            """,
                            (initiator["name"], partner["name"]),
                        )
                        self.conn.commit()
                        outcome = (
                            f"{initiator['name']} and {partner['name']} met to coordinate "
                            f"their ongoing criminal alliance."
                        )
            except Exception as e:
                logger.error(f"[Alliance] DB error: {e}")

        return outcome, {"alliance_type": alliance_type}

    def _expand_gang(
        self, agent_a: dict, agent_b: dict, day: int
    ) -> tuple[str, dict]:
        """Gang leader recruits thief into gang operations."""
        if agent_a["role"] == "gang_leader":
            leader, recruit = agent_a, agent_b
        else:
            leader, recruit = agent_b, agent_a

        outcome = (
            f"{leader['name']} expanded criminal operations with {recruit['name']}. "
            f"Gang strength increases."
        )
        return outcome, {"gang_expansion": True}

    def _attempt_compromise(
        self, agent_a: dict, agent_b: dict, day: int
    ) -> tuple[str, dict]:
        """
        Criminal tries to flip target. Target rolls loyalty check.
        Success (30%): target compromised.
        Failure (70%): criminal's intent reported to police.
        """
        # Determine who is trying to compromise whom
        criminal_roles = {"blackmailer", "gang_leader", "thief"}
        if agent_a["role"] in criminal_roles:
            criminal, target = agent_a, agent_b
        else:
            criminal, target = agent_b, agent_a

        roll = random.random()
        if roll < 0.30:
            # Compromise succeeds
            outcome = (
                f"{criminal['name']} successfully pressured {target['name']} into cooperation. "
                f"{target['name']} is now compromised."
            )
            return outcome, {"compromise": "success", "target": target["name"]}
        else:
            # Target resists and reports
            outcome = (
                f"{target['name']} refused {criminal['name']}'s attempt at coercion "
                f"and will report the encounter to the authorities."
            )
            return outcome, {"compromise": "failed", "reported": criminal["name"]}

    def _debrief_informant(
        self, agent_a: dict, agent_b: dict, day: int
    ) -> tuple[str, dict]:
        """
        Police gains intelligence from informant.
        Elevates event_log visibility on known suspects.
        """
        if agent_a["role"] == "police":
            police, informant = agent_a, agent_b
        else:
            police, informant = agent_b, agent_a

        outcome = (
            f"{police['name']} debriefed informant {informant['name']}. "
            f"Intelligence on criminal activity has been updated."
        )
        return outcome, {"intelligence_gain": True, "informant": informant["name"]}

    def _trade_goods(
        self, agent_a: dict, agent_b: dict, day: int
    ) -> tuple[str, dict]:
        """Merchant and healer exchange tokens for goods/medicine."""
        trade_amount = random.randint(50, 150)
        if agent_a["role"] == "merchant":
            seller, buyer = agent_a, agent_b
        else:
            seller, buyer = agent_b, agent_a

        outcome = (
            f"{seller['name']} traded medical supplies to {buyer['name']} "
            f"for {trade_amount} tokens."
        )
        return outcome, {"trade_amount": trade_amount}

    def _start_project(
        self, agent_a: dict, agent_b: dict, day: int
    ) -> tuple[str, dict]:
        """Builder meets collaborator — project work is advancing."""
        outcome = (
            f"{agent_a['name']} and {agent_b['name']} coordinated on construction work. "
            f"Project progress advances."
        )
        return outcome, {"project_advance": True}

    def _social_meeting(
        self, agent_a: dict, agent_b: dict, day: int
    ) -> tuple[str, dict]:
        """Generic meeting with no special mechanical outcome."""
        outcomes = [
            f"{agent_a['name']} and {agent_b['name']} had a friendly conversation.",
            f"{agent_a['name']} shared news with {agent_b['name']}.",
            f"{agent_a['name']} and {agent_b['name']} exchanged ideas.",
        ]
        return random.choice(outcomes), {}

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _record_meeting(
        self,
        day: int,
        participants: list[str],
        location: str,
        outcome: str,
    ) -> None:
        """Writes a meeting_events row to the database."""
        if self.conn is None:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO meeting_events (day, participants, location, outcome)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (day, participants, location, outcome[:255]),
                )
            self.conn.commit()
        except Exception as e:
            logger.error(f"[Meeting] DB record error: {e}")

    # ── Intent detection ──────────────────────────────────────────────────────

    def _has_meeting_intent(self, agent_a: dict, agent_b: dict) -> bool:
        """
        Returns True if either agent's last message or last action
        contains a meeting-intent keyword AND the other agent's name is mentioned
        (or the message is generally about meeting).
        """
        text_a = " ".join([
            (agent_a.get("last_message") or ""),
            (agent_a.get("last_action") or ""),
        ]).lower()

        text_b = " ".join([
            (agent_b.get("last_message") or ""),
            (agent_b.get("last_action") or ""),
        ]).lower()

        name_a_lower = agent_a["name"].split()[0].lower()
        name_b_lower = agent_b["name"].split()[0].lower()

        def has_intent(text: str, other_name: str) -> bool:
            has_keyword = any(w in text for w in MEETING_INTENT_WORDS)
            mentions_other = other_name in text
            return has_keyword and mentions_other

        return (
            has_intent(text_a, name_b_lower)
            or has_intent(text_b, name_a_lower)
        )
