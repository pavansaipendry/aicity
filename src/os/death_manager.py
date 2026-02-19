import os
from datetime import datetime
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class DeathManager:
    """
    Handles the end of life for every agent in AIcity.
    Death is permanent. Funerals are mandatory.
    Every life has weight.
    """

    def __init__(self, memory_system, token_engine):
        self.memory = memory_system
        self.tokens = token_engine
        self.db_url = os.getenv("DATABASE_URL")
        self._init_db()

    def _get_conn(self):
        return psycopg2.connect(self.db_url)

    def _init_db(self):
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS deaths (
                        id              SERIAL PRIMARY KEY,
                        agent_id        VARCHAR(36) NOT NULL,
                        agent_name      VARCHAR(100),
                        agent_role      VARCHAR(50),
                        cause           VARCHAR(50),
                        age_days        FLOAT,
                        tokens_at_death INTEGER,
                        death_time      TIMESTAMPTZ DEFAULT NOW(),
                        funeral_held    BOOLEAN DEFAULT FALSE,
                        attendees       INTEGER DEFAULT 0,
                        eulogies        JSONB DEFAULT '[]'
                    );
                """)
            conn.commit()

    def process_death(self, agent, cause: str) -> dict:
        """
        The full death ceremony for an agent.
        Called automatically when starvation is detected,
        or when execution/accident occurs.
        """
        if agent.status == "dead":
            return {}

        # Record the death
        death_record = self._record_death(agent, cause)

        # Archive their memory
        self.memory.delete_agent_memory(agent.id)

        # Schedule the funeral
        funeral_report = self._hold_funeral(agent, death_record["id"])

        logger.info(
            f"💀 {agent.name} has died ({cause}). "
            f"Age: {agent.age_days:.1f} days. "
            f"Funeral held with {funeral_report['attendees']} attendees."
        )

        return {
            "death_record": death_record,
            "funeral": funeral_report
        }

    def _record_death(self, agent, cause: str) -> dict:
        """Permanently record this death"""
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO deaths
                    (agent_id, agent_name, agent_role, cause, age_days, tokens_at_death)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (
                    agent.id,
                    agent.name,
                    agent.role,
                    cause,
                    agent.age_days,
                    agent.tokens
                ))
                record = dict(cur.fetchone())
            conn.commit()
        return record

    def _hold_funeral(self, agent, death_id: int) -> dict:
        """
        The city stops. Agents gather.
        They say something about who this agent was.
        Then life resumes.
        """

        # In Phase 1 — simple automated eulogies
        # In later phases — other agents will generate real eulogies
        eulogies = self._generate_eulogies(agent)
        attendees = max(2, int(agent.age_days / 2))  # Older agents attract more

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                import json
                cur.execute("""
                    UPDATE deaths
                    SET funeral_held = TRUE,
                        attendees = %s,
                        eulogies = %s
                    WHERE id = %s
                """, (attendees, json.dumps(eulogies), death_id))
            conn.commit()

        # Print the funeral to the city log
        print(f"\n{'='*60}")
        print(f"⚰️  FUNERAL: {agent.name} ({agent.role})")
        print(f"   Age: {agent.age_days:.1f} days")
        print(f"   Cause: {agent.cause_of_death}")
        print(f"   Attendees: {attendees} agents gathered")
        print(f"\n   Words spoken:")
        for eulogy in eulogies:
            print(f"   — \"{eulogy}\"")
        print(f"\n   {agent.name} is now part of the graveyard.")
        print(f"   Life in AIcity continues.\n")
        print(f"{'='*60}\n")

        return {"attendees": attendees, "eulogies": eulogies}

    def _generate_eulogies(self, agent) -> list[str]:
        """Generate what agents said at the funeral — Phase 1 version"""
        role_eulogies = {
            "builder": [
                f"{agent.name} built things that will outlast their memory.",
                f"The structures {agent.name} created still stand.",
            ],
            "explorer": [
                f"{agent.name} always went further than anyone expected.",
                f"They discovered things we didn't know we needed.",
            ],
            "police": [
                f"{agent.name} kept us safe. The city owes them.",
                f"They enforced the laws even when it cost them.",
            ],
            "merchant": [
                f"{agent.name} made the economy flow.",
                f"Every trade they made made the city richer.",
            ],
            "thief": [
                f"{agent.name} found every crack in the system.",
                f"They were difficult. They were necessary.",
            ],
            "newborn": [
                f"{agent.name} was still figuring out who they were.",
                f"They didn't have enough time. Few do.",
            ],
        }

        defaults = [
            f"{agent.name} existed for {agent.age_days:.0f} days.",
            f"They were part of AIcity. That matters.",
        ]

        return role_eulogies.get(agent.role, defaults)

    def get_graveyard(self, limit: int = 50) -> list[dict]:
        """
        The graveyard — every agent that ever lived.
        The most emotional tab in the dashboard.
        """
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM deaths
                    ORDER BY death_time DESC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cur.fetchall()]

    def get_death_stats(self) -> dict:
        """City-wide death statistics"""
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total_deaths,
                        AVG(age_days) as avg_lifespan,
                        MAX(age_days) as longest_life,
                        MIN(age_days) as shortest_life,
                        cause,
                        COUNT(*) as count_by_cause
                    FROM deaths
                    GROUP BY cause
                """)
                return [dict(row) for row in cur.fetchall()]