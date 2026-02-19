"""
main_phase3.py — Entry point for AIcity Phase 3.

What's new vs Phase 2:
    - Real token transfers (theft actually moves tokens from victim)
    - Trial system (arrests trigger LLM judge verdicts)
    - Births (population floor — city never goes extinct)
    - Persistent state (PostgreSQL save/load — city survives restarts)
    - Relationships (bond tracking between agents)
    - Live dashboard (http://localhost:8000)

Requirements:
    - ANTHROPIC_API_KEY in .env
    - OPENAI_API_KEY in .env
    - Docker running (Redis, Qdrant)
    - PostgreSQL running locally (createdb aicity + run migrations)
    - Dashboard (optional): uvicorn src.dashboard.server:app --port 8000

Run:
    python main_phase3.py
"""

import os
from dotenv import load_dotenv
load_dotenv()

from src.os.city_v3 import AICity
from src.memory.persistence import CityPersistence

if __name__ == "__main__":
    city = AICity()
    persistence = CityPersistence()

    # Load existing city OR start fresh
    saved = persistence.load_city()
    if saved:
        city.load_from_save(saved)
        print(f"🔄 Resuming AIcity from Day {saved['day']}")
    else:
        city.big_bang(n=10)
        print("🌌 New city created — Day 1")

    city.run(days=30, speed=120, persistence=persistence)