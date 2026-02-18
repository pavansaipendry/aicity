import os
import redis
import psycopg2
from qdrant_client import QdrantClient
from dotenv import load_dotenv

load_dotenv()

def verify_redis():
    r = redis.from_url(os.getenv("REDIS_URL"))
    r.set("test", "aicity_alive")
    result = r.get("test")
    assert result == b"aicity_alive"
    print("✅ Redis — connected")

def verify_postgres():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print("✅ PostgreSQL — connected")
    conn.close()

def verify_qdrant():
    client = QdrantClient(url=os.getenv("QDRANT_URL"))
    collections = client.get_collections()
    print("✅ Qdrant — connected")

def verify_env():
    required = ["ANTHROPIC_API_KEY", "AICITY_STARTING_TOKENS", "PAVAN_RED_BUTTON_KEY"]
    for key in required:
        assert os.getenv(key), f"Missing env var: {key}"
    print("✅ Environment variables — all present")

if __name__ == "__main__":
    print("\n🏙️  AIcity Environment Verification\n")
    verify_env()
    verify_redis()
    verify_postgres()
    verify_qdrant()
    print("\n✅ All systems go. AIcity is ready to build.\n")