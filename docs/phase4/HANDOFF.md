# AIcity Phase 4 — Handoff Document
> Read this at the start of every new session. Everything needed to continue is here.

---

## Quick State

- **Phase 4 Stages 1–5: COMPLETE** (all critical gaps fixed as of last session)
- **Stage 6 (Visual City / Phaser.js): NOT started — user chose to defer**
- **Code is ready to run** — only thing needed is a `.env` file with API keys

---

## How to Run

```bash
cd /Users/pavansaipendry/Desktop/AI City/aicity

# 1. Make sure Docker services are up (they usually stay up)
docker ps   # should show: aicity-postgres-1, aicity-redis-1, aicity-qdrant-1

# 2. Create .env from template (if not exists)
cp env.example .env
# then fill in: ANTHROPIC_API_KEY, OPENAI_API_KEY, GROQ_API_KEY

# 3. Run all migrations (safe to re-run — all use IF NOT EXISTS)
for f in src/migrations/*.sql; do
  PGPASSWORD=aicity psql -h 127.0.0.1 -p 5433 -U aicity -d aicity -f $f
done

# 4. Run the simulation
.venv/bin/python main_phase3.py

# 5. (Optional) Dashboard
uvicorn src.dashboard.server:app --port 8000
```

---

## Infrastructure

| Service | Port | Credentials |
|---|---|---|
| PostgreSQL (Docker) | 5433 | `aicity:aicity@127.0.0.1:5433/aicity` |
| Redis (Docker) | 6379 | default |
| Qdrant (Docker) | 6333 | default |

`.env` template is at `env.example`. The DB URL in env.example already matches Docker.

---

## All DB Tables (confirmed existing)

| Table | Purpose |
|---|---|
| `agents` | All agents — name, role, tokens, mood_score, bribe_susceptibility, etc. |
| `agent_balances` | Per-agent token balances |
| `agent_snapshots` | Daily state snapshots for persistence |
| `token_transactions` | Full ledger of every token movement |
| `city_vault` | Vault balance |
| `event_log` | Every crime/event with visibility state (PRIVATE→PUBLIC) |
| `police_cases` | Police complaint book — cases, notes, suspects, reports |
| `gangs` | Gang name, leader, members[], total_crimes, known_to_police |
| `city_assets` | Built infrastructure — watchtower, hospital, school, etc. |
| `shared_projects` | In-progress collaborative builds |
| `stories` | Daily/weekly/monthly newspapers saved to DB |
| `graduations` | Newborn graduation records |
| `deaths` | Death records |
| `crimes` | Crime records |
| `messages` | Redis message log |
| `newspapers` | Legacy newspaper table |
| `city_meta` | City metadata |

---

## Migration Files

```
src/migrations/
  001_initial_schema.sql      — agents, balances, vault, transactions
  002_newborn_comprehension.sql — comprehension_score, assigned_teacher
  003_stories.sql             — stories table (newspaper archive)
  004_event_log.sql           — event_log table (Stage 1)
  005_mood.sql                — mood_score column on agents (Stage 2)
  006_police_cases.sql        — police_cases table (Stage 3)
  007_villains.sql            — gangs table, bribe_susceptibility column (Stage 4)
  008_city_infrastructure.sql — city_assets + shared_projects tables (Stage 5)
```

---

## Key Source Files

```
src/
  os/
    city_v3.py              ← MAIN SIMULATION RUNNER — all wiring lives here
  agents/
    agent.py                ← Agent class, AgentRole enum (includes GANG_LEADER)
    brain.py                ← LLM decision engine — all role prompts, bond injection
    behaviors.py            ← execute_action() + all role handlers
    factory.py              ← spawn_founding_citizens(), bribe_susceptibility set here
    gang.py                 ← GangSystem — formation, bonuses, exposure, breaking
    newspaper.py            ← CityNewspaper — daily/weekly/monthly + archive flag
    messaging.py            ← Redis send/get inbox
    relationships.py        ← RelationshipTracker — bond scores
    births.py               ← (unused — birth logic is in city_v3._spawn_new_agent)
  economy/
    token_engine.py         ← Core balance engine (earn/spend/burn)
    transfers.py            ← TransferEngine — real bilateral theft
    projects.py             ← ProjectSystem — joint builds, progress, completion
    assets.py               ← AssetSystem — daily benefits, destruction, evidence trail
  justice/
    case_manager.py         ← Police complaint book + investigation loop
    court.py                ← Court — files cases, runs verdicts
    judge.py                ← JudgeAgent LLM
  city/
    event_log.py            ← EventLog — visibility state machine, witness detection
  memory/
    memory_v2.py            ← AgentMemory (Qdrant) + CityKnowledge
    persistence.py          ← CityPersistence — PostgreSQL save/load
  dashboard/
    server.py               ← FastAPI + WebSocket dashboard
```

---

## Stage-by-Stage Status

### Stage 1 — The Eyes ✅ COMPLETE
- `event_log` table and `src/city/event_log.py` fully built
- Visibility state machine: PRIVATE → WITNESSED → RUMOR → REPORTED → PUBLIC
- All crime events logged with initial visibility PRIVATE
- Witnesses detected via `detect_witnesses()` → stores Qdrant memory fragment
- `file_report()` promotes events to REPORTED, opens police case
- **Newspaper filters to PUBLIC event types only** (implemented in city_v3.simulate_day)

### Stage 2 — The Heart ✅ COMPLETE
- `mood_score` float (−1.0 to +1.0) on every agent
- All mood triggers wired:
  - Theft victim: −0.20
  - Asset destroyed: −0.30 (all alive agents except saboteur)
  - Cold case / no justice: −0.15 to complainant
  - Welfare received: +0.10
  - Justice served (guilty verdict): +0.20 to police, +0.05 to all
  - Good earnings (>250): +0.07
  - Healer healed you: +0.15 (new "heal" event type)
- Bond injection in brain prompts: `_build_relationship_section()` with role-specific guidance
- Mood converted to rich descriptive text (`_mood_score_to_text()`) before LLM sees it
- Susceptibility note injected when mood < −0.70 ("you are at a breaking point")

### Stage 3 — The Law ✅ COMPLETE
- `police_cases` table with full case lifecycle
- `CaseManager` in `src/justice/case_manager.py`:
  - `check_victim_reports()` — 60% chance victims file formal reports each day
  - `run_daily_investigation()` — police LLM writes case notes, requests arrests
  - Returns `(arrest_requests, cold_case_victims)` tuple
  - `close_case_solved()` / `_close_case_cold()` — LLM writes closing report
  - `reopen_case()` — cold cases can be reopened with new evidence
- COLD_CASE_DAYS = 14
- Police LLM (Claude Sonnet) only sees WITNESSED/REPORTED/PUBLIC evidence

### Stage 4 — The Villains ✅ COMPLETE

**Gang Leader role:**
- Added to AgentRole enum, brain prompts, factory (10th founding slot)
- `_gang_leader` behavior: finds mood < −0.70 agents, sends Redis recruitment messages
- `GangSystem` (src/agents/gang.py):
  - `run_daily()` — 30% chance formation if 2+ recruitable agents exist
  - `get_gang_bonus()` — returns 1.4× (leader), 1.2× (member), 1.0× (solo)
  - Gang bonus injected into agent_dict in city_v3._agent_turn before execute_action
  - `expose_gang_member()` — 40% chance arrested member talks → RUMOR
  - `break_gang()` — leader convicted → gang collapses
- MIN_GANG_SIZE = 3, RECRUIT_MOOD_THRESHOLD = −0.70

**Saboteur role:**
- `_saboteur` behavior: logs as PRIVATE
- `_handle_saboteur_asset_attack()` in city_v3:
  - Picks random standing asset, calls `destroy_asset()`
  - All alive agents (except saboteur) get −0.30 mood
  - Evidence trail: "scorch marks", "tools found nearby", etc.

**Blackmailer role:**
- `_blackmailer` behavior queries `event_log.get_events_known_to_agent()` first
- Targets agents with real witnessed crimes (PRIVATE/WITNESSED/RUMOR where actor ≠ self)
- Falls back to wealthy random targets if no real leverage found
- Non-payment → 30% chance escalates to REPORTED via `file_report()`

**Corrupt Police:**
- `bribe_susceptibility` float set at agent birth in factory.py (random 0.0–0.85)
- Never shown in dashboard, logs, or newspaper
- Thief sends bribe offer to police inbox (20% chance after successful theft)
- `_check_police_bribe()` in city_v3: rolls against susceptibility, transfers tokens silently if accepted
- **Susceptibility injected into police brain prompt** (shapes case-writing personality):
  - ≥0.60: "pragmatic, makes problems disappear quietly"
  - 0.30–0.59: "not naive, understands why some bend rules"
  - <0.30: no note (honest officer)
- **Susceptibility drift**:
  - Accepts bribe → +0.03
  - Guilty verdict witnessed → −0.02

### Stage 5 — The City ✅ COMPLETE

**ProjectSystem** (`src/economy/projects.py`):
- 6 asset types: watchtower, hospital, market_stall, school, road, archive
- `start_project()`, `join_project()`, `contribute()`, `update_daily()`
- Progress: +1.0 if all required contributors active that day, +0.5 if partial
- ABANDON_DAYS = 3
- `best_startable_project()` uses BUILD_PRIORITY order

**AssetSystem** (`src/economy/assets.py`):
- `apply_daily_benefits()` called BEFORE agent turns:
  - watchtower → police +30/day
  - hospital → healer +40/day
  - market_stall → merchants split 50/day
  - school → teacher +30/day
  - road → explorer +25/day
  - archive → flag only (no tokens)
- `get_asset_flags()` returns `{"watchtower": True, ...}` — passed to execute_action
- `destroy_asset()` — PRIVATE log with evidence trail

**Behavior bonuses (asset_flags wired through):**
- Police arrest chance: 0.25 → 0.30 when watchtower exists
- Newborn comprehension growth: ×2.0 when school exists

**Vault redistribution** (end of each day):
- Welfare: balance < 200 → +100 from vault
- Public goods: vault > 5000 → fund active project progress OR community +50 to all

**Archive → Newspaper:**
- `newspaper.write()` accepts `archive_active=False`
- When archive exists, messenger writes with "historical precision" — cites names/numbers/dates

---

## Key Architectural Rules (do NOT break these)

1. **Newspaper = PUBLIC events only.** Filter in `simulate_day` using `_NEWSPAPER_PUBLIC_TYPES`. Private crimes must never appear.
2. **Police investigation = DB evidence only.** `get_evidence_for_police()` returns WITNESSED/REPORTED/PUBLIC. No god-view.
3. **bribe_susceptibility is NEVER logged, displayed, or broadcast.** It only influences LLM prompt.
4. **Gang formation is probabilistic, not scripted.** GANG_FORMATION_CHANCE = 0.30.
5. **event_log visibility is a state machine** — events can only move forward (PRIVATE → … → PUBLIC), never backward.
6. **`run_daily_investigation()` returns a tuple** `(arrest_requests: list[dict], cold_case_victims: list[str])`. Both sides must be unpacked in city_v3.

---

## Deferred (known gaps, not urgent)

- **Recruited non-criminal gang members gaining criminal behaviors** — when a builder joins a gang, their behavior.py function currently doesn't change. Implementing this requires behavioral routing overhaul. Low priority.
- **Stage 6 — Visual City (Phaser.js)** — user explicitly chose to defer.

---

## LLM Routing

| Role | Model |
|---|---|
| police, lawyer | Claude Sonnet |
| builder, healer, teacher, explorer, thief, newborn, gang_leader, blackmailer, saboteur | GPT-4o |
| merchant, messenger | Llama 3.3 via Groq (free) |
| police investigation (case_manager) | Claude Sonnet |
| graduation | GPT-4o |
| monthly chronicle | Claude Sonnet |

---

## What to Do Next Session

1. **Create `.env` file** (copy from `env.example`, fill in API keys)
2. **Run migrations** (if any new ones were added)
3. **Run the simulation**: `.venv/bin/python main_phase3.py`
4. Fix any runtime errors discovered during the actual run
5. After confirming run is stable → decide: Stage 6 (visual city) OR other improvements

---

## Files Modified in Phase 4 (full list)

| File | What changed |
|---|---|
| `src/agents/agent.py` | Added `GANG_LEADER` to AgentRole enum |
| `src/agents/brain.py` | Role prompts for gang_leader/blackmailer/saboteur; bond injection; mood text; corruption note for police |
| `src/agents/behaviors.py` | `execute_action` + all villain handlers; `asset_flags` param; gang bonus; school ×2; watchtower detection; blackmailer event_log targeting; heal event |
| `src/agents/factory.py` | Added gang_leader to founding roles; `bribe_susceptibility` set at birth |
| `src/agents/gang.py` | New file — GangSystem |
| `src/agents/newspaper.py` | `archive_active` param for richer chronicles |
| `src/justice/case_manager.py` | Full complaint book; `run_daily_investigation` returns tuple with cold_case_victims |
| `src/economy/projects.py` | New file — ProjectSystem |
| `src/economy/assets.py` | New file — AssetSystem |
| `src/os/city_v3.py` | All wiring: newspaper filter, gang bonus injection, asset_flags, cold case mood, heal mood, bribe susceptibility in context, susceptibility drift, saboteur -0.30 mood, archive flag |
| `src/city/event_log.py` | New file — EventLog with full visibility state machine |
| `src/migrations/004–008.sql` | All Phase 4/5 DB migrations |
