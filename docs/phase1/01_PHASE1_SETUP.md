# Phase 1 — Step 1: Environment Setup

**Date:** February 2026
**Status:** ⏳ To Do
**Goal:** Set up the full development environment for AIcity.

---

## What We're Building

Before writing a single line of AIcity logic, we need a clean, reproducible environment. Every developer who joins later should be able to clone the repo and be running in under 10 minutes.

---

## Prerequisites

Make sure you have these installed on your machine:

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Primary language |
| Docker Desktop | Latest | Agent containers |
| Git | Latest | Version control |
| VS Code | Latest | IDE |
| Node.js | 18+ | Dashboard (later) |

---

## Step-by-Step Setup

### 1. Create the project folder structure

```bash
mkdir aicity
cd aicity

mkdir -p src/agents
mkdir -p src/economy
mkdir -p src/memory
mkdir -p src/os
mkdir -p src/security
mkdir -p src/dashboard
mkdir -p tests
mkdir -p docs
mkdir -p logs
mkdir -p scripts
```

**Why this structure?**
Each folder maps to a layer of OASAI. Keeps things clean as the project grows. When we have 10 developers, everyone knows where everything lives.

---

### 2. Create the Python virtual environment

```bash
python -m venv venv

# Mac/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**Why a virtual environment?**
Isolates AIcity's dependencies from everything else on your machine. No version conflicts.

---

### 3. Create requirements.txt

```bash
touch requirements.txt
```

Add this to requirements.txt:

```txt
# Agent Frameworks
langgraph==0.2.0
crewai==0.80.0
autogen==0.4.0

# LLMs
anthropic==0.40.0
openai==1.58.0
ollama==0.4.0

# Memory
qdrant-client==1.12.0
redis==5.2.0
psycopg2-binary==2.9.10

# Database
sqlalchemy==2.0.36

# Security
guardrails-ai==0.5.0

# Utilities
python-dotenv==1.0.1
pydantic==2.10.0
loguru==0.7.3
rich==13.9.4
pytest==8.3.4
```

Install everything:

```bash
pip install -r requirements.txt
```

---

### 4. Create the .env file

```bash
touch .env
```

Add this to .env — fill in your actual keys:

```env
# LLM Keys
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Memory
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
DATABASE_URL=postgresql://aicity:aicity@localhost:5432/aicity

# AIcity Config
AICITY_MAX_AGENTS=1000
AICITY_STARTING_TOKENS=1000
AICITY_DAILY_BURN_RATE=100
AICITY_MAX_TOKEN_SUPPLY=10000000
AICITY_TAX_RATE=0.10

# Security
PAVAN_RED_BUTTON_KEY=generate_a_very_long_random_string_here
SECRET_KEY=another_very_long_random_string_here

# Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

**CRITICAL:** Add .env to .gitignore immediately. Never commit keys to GitHub.

```bash
echo ".env" >> .gitignore
echo "venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
echo "logs/" >> .gitignore
```

---

### 5. Start the infrastructure with Docker

Create docker-compose.yml:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: aicity
      POSTGRES_USER: aicity
      POSTGRES_PASSWORD: aicity
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  redis_data:
  postgres_data:
  qdrant_data:
```

Start everything:

```bash
docker-compose up -d
```

Verify all three services are running:

```bash
docker-compose ps
```

You should see redis, postgres, and qdrant all showing "Up".

---

### 6. Initialize Git

```bash
git init
git add .
git commit -m "feat: initial AIcity project structure"
```

Create a repo on GitHub called `aicity` and push:

```bash
git remote add origin https://github.com/YOUR_USERNAME/aicity.git
git push -u origin main
```

---

### 7. Verify everything works

Create a test file `scripts/verify_setup.py`:

```python
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
```

Run it:

```bash
python scripts/verify_setup.py
```

If you see all four checkmarks — your environment is ready.

---

## What We Have After This Step

```
aicity/
├── src/
│   ├── agents/
│   ├── economy/
│   ├── memory/
│   ├── os/
│   ├── security/
│   └── dashboard/
├── tests/
├── docs/
├── logs/
├── scripts/
│   └── verify_setup.py
├── docker-compose.yml
├── requirements.txt
├── .env
└── .gitignore
```

Three databases running. All dependencies installed. Keys configured. Ready for Step 2.

## ⚠️ Mac Note — Port Conflict
If you have another PostgreSQL running locally (e.g. from Homebrew or another project),
it will conflict with Docker on port 5432.
Fix: Change Docker's postgres port to 5433 in docker-compose.yml
and update DATABASE_URL in .env to use port 5433.

---

## Next Step

→ [02_PHASE1_AGENT.md](./02_PHASE1_AGENT.md) — Build the Agent class