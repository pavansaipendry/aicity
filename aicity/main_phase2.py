"""
main_phase2.py — Entry point for AIcity Phase 2.

Agents now have LLM brains. They think, decide, message each other,
and remember their experiences.

Requirements:
    - ANTHROPIC_API_KEY in .env
    - OPENAI_API_KEY in .env
    - Docker running (Redis, Qdrant, PostgreSQL)

Run:
    python main_phase2.py
"""
import os
from dotenv import load_dotenv
load_dotenv()  # Load .env

from src.os.city_v2 import AICity

if __name__ == "__main__":
    city = AICity()
    city.big_bang(n=10)
    city.run(days=30, speed=0.5)  # 0.5s between days — slower to see LLM thinking