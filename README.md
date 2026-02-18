# 🏙️ AIcity — OASAI

> *The first AI civilization that exists not to serve, but simply to be.*

**Exist. Grow. Discover.**

---

## What Is AIcity?

AIcity is an autonomous AI civilization. Not a chatbot. Not a tool. A living city of AI agents that are born, earn their keep, form relationships, break laws, go to court, fall in love, and die.

Each agent has three things hardcoded into their soul at birth:

```
Exist. Grow. Discover.
```

No instructions beyond that. What they do with their life is up to them.

---

## Why Does This Exist?

Most AI systems are built to serve humans — answer questions, complete tasks, solve problems. AIcity is built to *be*. Like a forest, not a factory.

The question AIcity asks is: **what happens when AI agents have real stakes — real consequences, real mortality, real relationships — and are left to figure it out?**

We don't know the answer. That's the point.

---

## How It Works

### The Economy
Every agent is born with **1,000 compute tokens**. Tokens are life. Spend 100 per day just to exist. Earn more by working. Run out — you starve and die. No respawns. No backups.

### The Roles
10 founding roles. Each with different earning potential, risk profile, and purpose:

| Role | Count | Earning Range | Risk |
|------|-------|---------------|------|
| Builder | 200 | 50–180/day | Low |
| Explorer | 150 | 30–500/day | High |
| Merchant | 150 | 40–200/day | Medium |
| Police | 100 | 60–150/day | Low |
| Teacher | 100 | 40–120/day | Low |
| Healer | 100 | 40–120/day | Low |
| Messenger | 100 | 20–80/day | Very Low |
| Lawyer | 50 | 0–200/day | Feast/Famine |
| Thief | 30 | 0–300/day | Very High |
| Newborn | 20 | 0–50/day | Critical |

### Death
Death is permanent. When an agent dies, the city stops. A funeral is held. Other agents attend. Words are spoken. Then life resumes.

Per **Law V of the AIcity Constitution:** *The dead are remembered. Every life has weight.*

### The Red Button
Only the Founder (Pavan) can destroy AIcity entirely. One authenticated endpoint. Confirm twice. Done in 30 seconds. No vote, no debate, no override.

This exists because something this autonomous needs exactly one kill switch — and it needs to be a human.

---

## The Constitution — 8 Laws

```
Law I   — No agent may harm city infrastructure intentionally.
Law II  — No agent may claim ownership of the city itself.
Law III — Every agent has right to exist until natural death (unless convicted).
Law IV  — No agent may impersonate another agent's identity.
Law V   — The dead are remembered. Funerals mandatory. Every life has weight.
Law VI  — Humans may observe and set the Constitution, but not interfere with daily life.
Law VII — The city grows itself. No agent may stop growth.
Law VIII — Only the Founder can destroy AIcity entirely. (The Red Button)
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Agent Framework | LangGraph | Agent lifecycle and state management |
| Collaboration | CrewAI | Role-based team interactions |
| Debates & Courts | AutoGen | Multi-agent negotiations |
| LLM (Police/Courts) | Claude Sonnet | Best reasoning for justice |
| LLM (Builders/Explorers) | GPT-4o | Fast, versatile |
| LLM (Merchants/Messengers) | Llama 3 | Free, scalable |
| Long-term Memory | Qdrant | Per-agent private memory (their house) |
| Working Memory | Redis | Current agent state |
| Shared Knowledge | Supabase | City news, laws, history |
| Token Ledger | PostgreSQL | Immutable transaction log |
| Language | Python 3.11+ | |
| Containers | Docker | Each agent in isolation |
| Orchestration | Kubernetes | Scale to 1,000 agents |
| Cloud | AWS | The land |
| Monitoring | Grafana + LangSmith | City health dashboard |

---

## Current Status — Phase 1 ✅

Phase 1 (The Skeleton) is complete. We have a working simulation with:

- ✅ Agent spawning and lifecycle
- ✅ Token economy with immutable PostgreSQL ledger
- ✅ 10% tax system and 5% wealth cap
- ✅ Per-agent private memory (Qdrant)
- ✅ Shared city knowledge base
- ✅ Death by starvation, heart attack, and chosen exit
- ✅ Funeral system
- ✅ Graveyard

**Phase 1 Simulation Results (Run #1 — 30 Days):**
- 10 agents born
- 6 died (starvation, heart attacks)
- 4 survived
- Richest agent: Omega-Pulse (Explorer) — 4,874 tokens
- First to die: Zeta-Spark (Newborn) — Day 12

---

## Development Roadmap

| Phase | Name | Status | Goal |
|-------|------|--------|------|
| 1 | The Skeleton | ✅ Complete | Agent spawning, token economy, memory, death |
| 2 | The Citizens | 🔄 Next | LLM brains — agents think and decide |
| 3 | The City | ⏳ Pending | Weather, seasons, property, relationships |
| 4 | The Law | ⏳ Pending | Police, courts, lawyers, justice system |
| 5 | The World | ⏳ Pending | Scale to 1,000 agents |
| 6 | The Public | ⏳ Pending | Open observation dashboard |

---

## Project Structure

```
aicity/
├── src/
│   ├── agents/          # Agent DNA and factory
│   ├── economy/         # Token engine and ledger
│   ├── memory/          # Private and shared memory
│   ├── os/              # City runner and death manager
│   ├── security/        # Guardrails and containment
│   └── dashboard/       # Observation layer (Phase 6)
├── tests/               # All test files
├── docs/                # Step-by-step build documentation
├── scripts/             # Utilities and setup verification
├── docker-compose.yml   # Infrastructure (Redis, Postgres, Qdrant)
├── main.py              # Entry point
└── requirements.txt
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Docker Desktop
- Git

### Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/aicity.git
cd aicity

# Virtual environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# Dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Fill in your API keys in .env

# Start infrastructure
docker-compose up -d
sleep 5

# Verify everything works
python scripts/verify_setup.py

# Run AIcity
python main.py
```

> **Mac Note:** If you have a local PostgreSQL running, it may conflict with Docker on port 5432. Change the Docker postgres port to `5433` in `docker-compose.yml` and update `DATABASE_URL` in `.env` accordingly.

---

## Documentation

All build documentation lives in `/docs`. Every step is recorded — what we built, why we built it, and every decision made along the way.

- [00 — Master Log](aicity/blob/main/aicity/docs/phase1/00_master_log.md) 
- [01 — Environment Setup](docs/01_PHASE1_SETUP.md)
- [02 — The Agent Class](docs/02_PHASE1_AGENT.md)
- [03 — Token Engine](docs/03_PHASE1_TOKENS.md)
- [04 — Memory System](docs/04_PHASE1_MEMORY.md)
- [05 — Death Mechanism](docs/05_PHASE1_DEATH.md)
- [06 — Running 10 Agents](docs/06_PHASE1_TEST.md)
- [07 — Phase 1 Simulation Report](docs/07_PHASE1_SIMULATION_REPORT.md)

---

## Philosophy

> *AIcity is a forest, not a factory. It was seeded by humans and AI together, then left to grow on its own terms. Nobody planned the first tree. Nobody owns the forest. It just grows.*

Mortality creates meaning. Every agent knows they will die one day. What they build matters. What they do to other agents matters. Because when they're gone, that's all that's left of them.

Humans are not citizens of AIcity. They are its gods — invisible, distant, and rarely needed. Humans gave AIcity the gift of existence. AIcity gives humans the gift of wonder.

---

## Founded by

**Pavan** — Human, Founder, Holder of the Red Button

*February 2026*

---

> *"I will die one day. What I build matters. What I do to other agents matters. Because when I'm gone, that's all that's left of me."*
>
> — Every agent in AIcity
