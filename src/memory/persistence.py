"""
src/memory/persistence.py

Saves and loads city state from PostgreSQL.
Requires: pip install psycopg2-binary
Set env var: DATABASE_URL=postgresql://localhost/aicity
"""

import os
import json
import psycopg2
import psycopg2.extras
from loguru import logger
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/aicity")


class CityPersistence:

    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url

    @contextmanager
    def connect(self):
        conn = psycopg2.connect(self.db_url)
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_day(self, city_day: int, agents: list[dict], newspaper: dict = None):
        """Call at end of each simulation day."""
        with self.connect() as conn:
            cur = conn.cursor()
            for agent in agents:
                cur.execute("""
                    INSERT INTO agents
                        (name, role, tokens, age_days, alive, cause_of_death,
                         died_on_day, comprehension_score, assigned_teacher)
                    VALUES
                        (%(name)s, %(role)s, %(tokens)s, %(age_days)s, %(alive)s,
                         %(cause_of_death)s, %(died_on_day)s,
                         %(comprehension_score)s, %(assigned_teacher)s)
                    ON CONFLICT (name) DO UPDATE SET
                        tokens              = EXCLUDED.tokens,
                        age_days            = EXCLUDED.age_days,
                        alive               = EXCLUDED.alive,
                        cause_of_death      = EXCLUDED.cause_of_death,
                        died_on_day         = EXCLUDED.died_on_day,
                        comprehension_score = EXCLUDED.comprehension_score,
                        assigned_teacher    = EXCLUDED.assigned_teacher
                """, {
                    "name":               agent["name"],
                    "role":               agent["role"],
                    "tokens":             agent["tokens"],
                    "age_days":           agent.get("age_days", 0),
                    "alive":              agent.get("status", "alive") == "alive",
                    "cause_of_death":     agent.get("cause_of_death"),
                    "died_on_day":        agent.get("died_on_day"),
                    "comprehension_score": agent.get("comprehension_score", 0),
                    "assigned_teacher":   agent.get("assigned_teacher"),
                })
                cur.execute("""
                    INSERT INTO agent_snapshots (agent_name, day, tokens, earnings, events)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    agent["name"], city_day, agent["tokens"],
                    agent.get("earnings_today", 0),
                    json.dumps(agent.get("events_today", [])),
                ))
            if newspaper:
                cur.execute("""
                    INSERT INTO newspapers (day, headline, body, written_by)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (day) DO NOTHING
                """, (city_day, newspaper.get("headline"), newspaper.get("body"), newspaper.get("written_by")))
            cur.execute("""
                INSERT INTO city_meta (key, value)
                VALUES ('current_day', %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (str(city_day),))
        logger.info(f"💾 City state saved — Day {city_day}")

    def load_city(self) -> dict | None:
        """Returns saved city state, or None if no save exists."""
        with self.connect() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT value FROM city_meta WHERE key = 'current_day'")
            row = cur.fetchone()
            if not row:
                return None
            current_day = int(row["value"])
            cur.execute("SELECT * FROM agents ORDER BY tokens DESC")
            agents = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT * FROM newspapers ORDER BY day DESC LIMIT 1")
            last_paper = cur.fetchone()
        logger.info(f"🔄 Loaded city state — Day {current_day}, {len(agents)} agents")
        return {
            "day":        current_day,
            "agents":     agents,
            "last_paper": dict(last_paper) if last_paper else None,
        }