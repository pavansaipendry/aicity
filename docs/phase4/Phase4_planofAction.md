# AIcity — Phase 4 Plan of Action
> Hand this file to Claude at the start of any new session. It has everything needed to continue.

---

## The Project in One Paragraph

AIcity is a persistent AI society simulation. Autonomous LLM agents are born, earn tokens, form relationships, steal, get arrested, die, and get buried — all without human interference. 10 founding agents. Daily token burn kills the broke ones. PostgreSQL for persistence, Redis for messaging, Qdrant for per-agent memory, FastAPI + WebSocket for the live dashboard. Think Dwarf Fortress meets a multi-agent AI experiment, with a Roblox-style visual future.

---

## What's Built and Working (Phases 1-3)

- Agents with real names, distinct roles (builder, explorer, merchant, police, teacher, healer, messenger, thief, newborn)
- Real token economy — theft moves tokens in DB, daily burn kills agents who run out
- PostgreSQL persistence — city survives restarts, resumes from last saved state
- Redis messaging — agents send messages to each other's inboxes
- Qdrant vector memory — per-agent private memory collections
- LLM brains — GPT-4o for most roles, Claude Sonnet for police/lawyer/chronicle
- Justice system — police arrests → Judge LLM reads evidence → verdict → fines executed
- Births — population floor of 6, new agents spawn automatically
- RelationshipTracker — bond scores (-1.0 to +1.0) between every agent pair
- Newborn graduation system — teacher assigned, comprehension score builds, LLM chooses final role
- Newspaper — daily (GPT-4o, 200w), weekly (400-600w), monthly chronicle (Claude Sonnet, 800-1200w), all saved to DB
- Live dashboard — FastAPI + WebSocket, agent cards, wealth chart, relationship SVG graph, dispatches feed, live events, graveyard, archives tab
- Refresh persistence — server holds city_state in memory, page reload restores everything

## What's Facade / Not Real Yet

- Collaboration is theater. Agents message each other but there's no joint action system. Two agents "agreeing to build" produces same result as working alone.
- Bond scores don't affect LLM decisions yet. Bonds are tracked but never injected into brain prompts.
- Vault accumulates taxes but does nothing — no redistribution, no welfare.
- No villain roles beyond one thief. No gangs, no saboteur, no blackmailer, no corrupt police.
- No information asymmetry — events are either all-known or all-unknown. No realistic evidence trail.
- No visual city — just text cards and SVG lines. Not watchable by a casual observer.

---

## Phase 4 Core Philosophy

**Three rules that govern every design decision:**

1. NO SCRIPTS. Nothing is predetermined. A gang might operate for 30 days undetected or get caught on day 2 by accident. Outcomes emerge from agent decisions, not from authored drama arcs.

2. INFORMATION ASYMMETRY. Every agent only knows what they personally witnessed or were told. The police investigates with incomplete evidence. The newspaper only reports what is publicly known. The player never gets a god-view — they piece things together the same way the agents do.

3. PEOPLE CHANGE. Agents accumulate memories that shift their behavior over time. A builder who watches his hospital burn twice starts making different decisions. No agent is permanently locked to a role or alignment. Drift is continuous and unscripted.

---

## Phase 4 Build Order

```
Stage 1 — The Eyes         (information asymmetry foundation)
Stage 2 — The Heart        (behavioral drift + bonds affect decisions)
Stage 3 — The Law          (police complaint book + real investigation)
Stage 4 — The Villains     (gang, saboteur, blackmailer, corrupt cops)
Stage 5 — The City         (joint actions + city infrastructure)
Stage 6 — The Visual City  (2D top-down canvas in browser)
```

Each stage enables the next. Do not skip ahead.

---

## Stage 1 — The Eyes (Information Asymmetry)

**Why first:** Everything in Phase 4 depends on this. Police investigations, newspaper reporting, villain stealth — all require events to have a known/unknown state.

### New DB table: event_log

```sql
CREATE TABLE event_log (
    id SERIAL PRIMARY KEY,
    day INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,   -- 'theft', 'arson', 'assault', 'bribe', 'blackmail', etc.
    actor_id VARCHAR(50),              -- who did it (may be NULL if unknown)
    target_id VARCHAR(50),             -- who it happened to
    asset_id INTEGER,                  -- if a city asset was involved
    description TEXT,                  -- plain text: "Zara stole 400 tokens from Marcus"
    visibility VARCHAR(20) DEFAULT 'PRIVATE',  -- PRIVATE / WITNESSED / RUMOR / REPORTED / PUBLIC
    witnesses TEXT[],                  -- agent IDs who saw it happen
    evidence_trail JSONB,              -- token ledger refs, memory refs, physical clues
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Visibility State Machine

```
PRIVATE   → Only the actor knows. No one else.
WITNESSED → 1+ agents were nearby and have a Qdrant memory of something happening.
            They may not know exactly what — just "I saw someone near the hospital at night."
RUMOR     → A witnessed agent told another agent via message. May be distorted.
            Multiple RUMOR states can exist with conflicting details.
REPORTED  → Victim or witness filed a formal report with police. Now in crime log.
PUBLIC    → Court issued a verdict, OR event spread widely enough (5+ agents know).
            Messenger can now write about it.
```

### Promotion Rules (how events move up the chain)

- `PRIVATE → WITNESSED`: Another agent was at the same location during the event. Their Qdrant memory gets: "I noticed something unusual near [location] on day [X]."
- `WITNESSED → RUMOR`: Witnessed agent sends a message to another agent mentioning what they saw.
- `RUMOR → REPORTED`: Any agent goes to the police and formally files a report.
- `REPORTED → PUBLIC`: Court verdict issued, OR police makes a public statement.
- Any state can jump to PUBLIC if 5+ agents know independently.

### Key Rule for the Messenger

The Messenger/Newspaper LLM prompt must ONLY include events where `visibility = 'PUBLIC'`. It cannot access PRIVATE, WITNESSED, or RUMOR events. The newspaper is always behind the truth. It reports history, not live intelligence.

### New file: `src/city/event_log.py`

Functions needed:
- `log_event(day, type, actor, target, description, location)` — creates PRIVATE entry
- `add_witness(event_id, agent_id, partial_description)` — promotes to WITNESSED, stores partial memory in Qdrant
- `spread_rumor(event_id, from_agent, to_agent)` — promotes to RUMOR
- `file_report(event_id, reporting_agent)` — promotes to REPORTED, creates police case
- `get_evidence_for_case(case_id)` — returns all evidence police can see for a case
- `get_public_events(day_range)` — returns only PUBLIC events, used by Messenger

### DB migration file: `src/migrations/004_event_log.sql`

---

## Stage 2 — The Heart (Behavioral Drift + Social Influence)

**Why second:** Once events are tracked, mood can respond to them. Once mood exists, bonds can meaningfully alter decisions.

### Mood Field on Agents

Add `mood FLOAT DEFAULT 0.0` to the agents DB table (range -1.0 to 1.0).

Mood update triggers:
```
Lost tokens to theft:           -0.20
Watched city asset destroyed:   -0.30
Filed police report, no action: -0.15 (each day case stays cold)
Received welfare payment:       +0.10
Ally helped them:               +0.15
Justice served (culprit caught): +0.20
Earned well today:              +0.05
Recruited by gang offer:        triggers susceptibility check (see Stage 4)
```

At mood < -0.70: agent becomes vulnerable to gang recruitment messages.
At mood < -0.90: agent may make extreme decisions (vigilante action, self-destruction, flight).

### Bond Injection into Brain Prompts

Every LLM brain call in `brain.py` must include relationship context. Before calling GPT-4o or Claude, pull top 3 positive bonds and top 2 negative bonds from RelationshipTracker and add to prompt:

```
Your known relationships today:
  Allies:  Maya (builder, bond +0.82), Rohan (teacher, bond +0.61), Felix (explorer, bond +0.40)
  Enemies: Zara (thief, bond -0.74), unknown arsonist (bond -0.50)

Factor this into your decision. You are more likely to help your allies,
more likely to avoid or retaliate against enemies.
```

Role-specific bond behavior:
- Thief: prefers targets with negative bond or neutral. Avoids attacking allies.
- Healer: prioritizes injured allies first, then neutrals, enemies last.
- Police: builds case priority list based on grudges. More motivated to solve crimes against allies.
- Builder: more likely to invite allies into joint projects.
- Gang Leader: targets low-mood agents with recruitment messages.

### DB migration file: `src/migrations/005_mood.sql`
### File changed: `src/agents/brain.py`

---

## Stage 3 — The Law (Police Complaint Book)

**Why third:** Needs Stage 1 (event_log) to exist first. Police investigation queries evidence that was logged there.

### New DB Table: police_cases

```sql
CREATE TABLE police_cases (
    id SERIAL PRIMARY KEY,
    day_opened INTEGER NOT NULL,
    complaint_text TEXT,                    -- what was reported
    complainant_id VARCHAR(50),             -- who reported it
    suspect_ids TEXT[],                     -- agents police currently suspect
    evidence JSONB,                         -- refs to event_log entries, token records, witness memories
    status VARCHAR(20) DEFAULT 'open',      -- open / investigating / solved / cold
    resolution TEXT,                        -- what actually happened (filled on close)
    police_report TEXT,                     -- LLM-written narrative of the investigation
    day_closed INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Police Daily Investigation Loop

Each day the police agent runs these steps (in `behaviors.py`):

1. Check for new REPORTED events → open a new case for each
2. For each open case, query available evidence:
   - Token transaction log (any suspicious transfers around that time?)
   - event_log entries with WITNESSED or higher visibility
   - Witness Qdrant memories related to the case
   - Informant messages from other agents
   - Pattern matches (same actor in multiple cases?)
3. Police LLM receives all this evidence and writes a daily case note (NOT a conclusion — just what they observed and what they plan to check next)
4. If evidence is strong enough → police files an arrest request
5. If no new evidence for 14 days → case goes COLD

### Police Case Report (written at close)

When a case resolves (arrest + verdict OR cold), the police LLM writes a full case report in plain language:
- What was initially reported
- What evidence was gathered
- What the investigation noticed (behavioral patterns, money trails, witness inconsistencies)
- How it was solved, OR why it went cold
- Any lingering suspicions even if no arrest was made

This goes into `police_cases.police_report`. Viewable in dashboard.
Cold cases stay in DB. New evidence can reopen them.

### Key Rule for Police

The police LLM prompt must ONLY include evidence that EXISTS in the DB at query time. It cannot know things that haven't been witnessed or reported. If no one saw it and no one reported it, the police has nothing to work with.

### New file: `src/justice/case_manager.py`

Functions needed:
- `open_case(reported_event_id, complainant_id)` — creates case from REPORTED event
- `add_evidence(case_id, evidence_ref)` — adds new evidence to open case
- `run_daily_investigation(police_agent)` — main loop, queries evidence, writes case note
- `close_case(case_id, resolution, report_text)` — marks solved or cold
- `reopen_case(case_id, new_evidence)` — cold case gets new lead

---

## Stage 4 — The Villains

**Why fourth:** Needs information asymmetry (Stage 1) so their crimes can be secret. Needs mood (Stage 2) so they can recruit. Needs police complaint system (Stage 3) so their crimes create real investigations.

### New Roles

**Gang Leader**
- Recruits low-mood agents (mood < -0.70) via private Redis messages
- If 3+ agents accept recruitment → gang is formally created in DB (`gangs` table: name, members[], day_formed, status)
- Coordinates attacks: gang members can hit the same target same day for multiplied damage
- Takes 20% cut of all criminal earnings from members
- Gang is NOT publicly known initially. It exists only in the private messages and DB.
- Becomes known (RUMOR) if a member gets arrested and talks, or if a message is intercepted

**Saboteur**
- Targets city assets (Stage 5 — assets must exist first before this has teeth)
- Destruction logged as PRIVATE in event_log
- Leaves evidence: "scorch marks", "tools found nearby", "footprints" — flavor text in evidence_trail JSONB
- Another agent at location that night gets a WITNESSED entry in their Qdrant memory ("I saw someone leaving the east district quickly that night")
- Asset status set to 'destroyed' in city_assets table

**Blackmailer**
- Queries event_log and crime history for agents with hidden crimes or unpaid debts
- Finds a wealthy agent with something to hide
- Sends private Redis message: "I know what you did on day 8. Pay me 400 tokens or I file a report."
- Target can: pay silently (token transfer), ignore (risk of exposure), report the blackmail to police (creates a new case), or try to find and expose the blackmailer
- Blackmailer tracks payment compliance. Non-payment → files the original report (promotes event to REPORTED)

**Corrupt Police**
- Not a separate role — it's a hidden attribute on regular police agents
- `bribe_susceptibility FLOAT` (0.0 to 1.0), set at creation, stored in DB, never shown in dashboard
- Score ranges:
  - 0.0 - 0.3: Honest. Refuses bribes. May notice corruption in others.
  - 0.3 - 0.6: Susceptible. Might look the other way on small crimes.
  - 0.6 - 1.0: Actively corrupt. Solicits bribes. Buries evidence. Writes cover-up reports.
- Bribe offer arrives as a private Redis message from criminal
- Police LLM decision is weighted by susceptibility score (hidden input to decision)
- If accepted: real token transfer (in ledger — traceable), case gets a plausible-sounding note that leads nowhere, case drifts to cold
- The corrupt cop writes technically-defensible case notes. Nothing overtly false. Holes are there if someone looks.
- Susceptibility drifts: unpunished corruption for 10+ days → score creeps up. Witnessing something horrific → drops.

**How Corrupt Police Gets Discovered (no script — any of these might happen):**
- Token trail: the bribe payment is in the transaction ledger. An honest second officer reviewing cold cases finds it.
- A gang member arrested on another charge makes a deal: "Reduce my fine, I'll name the cop on the payroll."
- Corrupt cop at extreme low mood confesses voluntarily.
- Pattern recognition: a new agent who becomes police reviews cold case archive, notices every case involving same criminal closed in 10 days.
- Corrupt cop gets greedy — takes a bribe too large, from a criminal whose victim was well-liked. Victim's allies raise enough noise it reaches RUMOR state.

**If Two Police Agents Exist:**
One might be corrupt, one honest. The honest one reviews cold cases. The corrupt one knows someone is looking and either covers tracks harder or tries to discredit the honest one. They might file competing case notes on the same investigation. The Judge LLM eventually rules on a case where the two officers' accounts directly contradict each other.

### Behavioral Change / Betrayal

Any agent at mood < -0.70 can receive a gang recruitment message.
Agents near starvation (< 200 tokens, 2 days from death) get a stronger susceptibility weight.
Accepting recruitment: agent's role doesn't change in name, but their behaviors.py function starts including criminal actions.
This is not announced to the city. The betrayal is only visible through the event_log over time.

### New files:
- `src/agents/gang.py` — gang formation, membership, coordination
- DB migration: `src/migrations/006_villains.sql` (gangs table, bribe_susceptibility column on agents)

---

## Stage 5 — The City (Infrastructure + Joint Actions)

**Why fifth:** Needs villain roles (Stage 4) to exist so that the saboteur has something real to destroy. Without city assets, destruction has no stakes.

### New DB Tables

```sql
-- City assets: persistent things the city builds
CREATE TABLE city_assets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,          -- "Northern Watchtower", "East Market", "School of Arts"
    asset_type VARCHAR(50),             -- 'watchtower', 'market', 'school', 'hospital', 'road'
    builders TEXT[],                    -- agent IDs who built it
    day_built INTEGER,
    status VARCHAR(20) DEFAULT 'standing',  -- standing / damaged / destroyed
    benefit_description TEXT,           -- human-readable: "Police earn +30 tokens/day on patrol"
    benefit_value JSONB,                -- machine-readable benefit config
    day_destroyed INTEGER
);

-- Shared projects: in-progress collaborative builds
CREATE TABLE shared_projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    project_type VARCHAR(50),
    creator_id VARCHAR(50),
    goal_days INTEGER,                  -- how many days of combined work needed
    contributors JSONB,                 -- {agent_id: days_contributed}
    progress INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',  -- active / completed / abandoned
    day_started INTEGER,
    day_completed INTEGER
);
```

### Asset Benefits (examples)

| Asset Type | Builders Needed | Days | Benefit |
|---|---|---|---|
| Watchtower | 2 builders | 4 days | Police earn +30/day on patrol. Thief detection +20%. |
| Hospital | 2 builders + healer | 5 days | Healer effectiveness x2. Sick agents recover faster. |
| Market Stall | merchant + builder | 3 days | Passive income 50 tokens/day. Agents trade at bonus. |
| School | teacher + 2 builders | 4 days | Newborns graduate 2x faster. Teacher earns more per student. |
| Road | explorer + builder | 2 days | Explorer discovers areas faster. New locations unlocked. |
| Archive | messenger + teacher | 3 days | Monthly chronicle richer. More structured city history. |

### Joint Action Rules

- Agent A starts a project → entry in shared_projects, sends invite message to Agent B
- Agent B joins next day (or same day if message processed first)
- Each day both agents contribute → +1 progress
- If only 1 agent contributes that day → +0.5 progress (partial credit)
- On completion: city_assets entry created. Project logged as PUBLIC event. Messenger can write about it.
- If project abandoned (no contributions for 3 days) → status = 'abandoned'

### Vault Redistribution

Add to end of daily city loop in `city_v3.py`:
- Welfare check: any agent with balance < 200 tokens receives 100 tokens from vault
- Public goods: if vault > 5,000 tokens, trigger a community bonus (all agents +50 tokens) OR auto-fund a pending project (pays for 1 day of progress)

### New files:
- `src/economy/projects.py` — project creation, joining, progress, completion
- `src/economy/assets.py` — asset creation, benefit application, destruction handling
- DB migration: `src/migrations/007_city_infrastructure.sql`

---

## Stage 6 — The Visual City (2D Top-Down Canvas)

**Why last:** The visual layer serves the simulation. It needs interesting things to show before it's worth building. Finish Stages 1-5 first.

### Technology Choice: Phaser.js (in the browser)

No new game engine. No Unity. No Godot. Phaser.js is a JavaScript 2D game library that runs in any browser. It replaces the center panel of the existing dashboard.

Why Phaser.js:
- Pure JavaScript, integrates with existing WebSocket client
- Tile-based map built in
- Sprite animations built in
- Runs in the same `index.html` as the current dashboard
- No separate game server needed

### What the Visual City Shows

- Simple grid city (20x20 tiles minimum)
- Buildings appear on tiles when assets are built
- Buildings show damage or become ruins when destroyed
- Agents are small labeled avatars that move between tiles each day
- Events trigger visual effects: fire animation on arson, shake animation on arrest, fade-out on death
- Hovering an agent shows their tooltip (name, role, tokens, mood, top bonds)
- Clicking an agent opens a full detail panel (see Agent Detail View below)

### Agent Positions in Simulation

Add `x INT, y INT` to agents table. Each day agents have a location on the grid:
- Builders: move toward active project tiles
- Police: patrol near last known crime location
- Thief: moves toward target agent's location
- Healer: moves toward sick/low-health agents
- Merchant: stays near market tile
- Messenger: moves around, central position
- Explorer: moves to undiscovered tiles

Position updates broadcast via WebSocket with every event. Frontend Phaser scene updates agent sprite positions.

### Dashboard Layout Change

Current center panel (newspaper/dispatches/archives tabs) becomes a side panel or collapsible. The visual city canvas becomes the main center view. Current panels still accessible but secondary.

### Agent Detail Panel

Click any agent → side panel slides open showing:
- Full life timeline (born day X, graduated day Y, arrested day Z, current status)
- Last 10 Qdrant memories (summarized)
- Bond history graph (mood trend over time)
- All messages sent and received (scrollable)
- Daily decision log (what the LLM chose each day and why)
- Current open police cases involving this agent (as victim or suspect)

### Case Files Tab in Dashboard

New tab alongside Daily/Economy/Dispatches/Archives:
- Lists all police cases, open and closed
- Click a case → reads the full `police_cases.police_report` text
- Cold cases shown in grey
- Solved cases show verdict and sentence
- Open cases show latest case note

### New files:
- `src/dashboard/static/city_canvas.js` — Phaser.js scene for the 2D city
- `src/dashboard/static/index.html` — updated layout with canvas center panel

---

## Full File Change Map

| Stage | New Files | Files Changed |
|---|---|---|
| 1 | `src/city/event_log.py`, `src/migrations/004_event_log.sql` | `src/agents/behaviors.py`, `src/os/city_v3.py` |
| 2 | `src/migrations/005_mood.sql` | `src/agents/brain.py`, `src/agents/agent.py` |
| 3 | `src/justice/case_manager.py`, `src/migrations/006_police_cases.sql` | `src/agents/behaviors.py`, `src/justice/court.py` |
| 4 | `src/agents/gang.py`, `src/migrations/007_villains.sql` | `src/agents/behaviors.py`, `src/agents/factory.py` |
| 5 | `src/economy/projects.py`, `src/economy/assets.py`, `src/migrations/008_city_infrastructure.sql` | `src/os/city_v3.py`, `src/agents/behaviors.py` |
| 6 | `src/dashboard/static/city_canvas.js` | `src/dashboard/static/index.html`, `src/dashboard/static/app.js`, `src/dashboard/server.py` |

---

## Current Stack (don't change any of this)

| Thing | What it's for |
|---|---|
| Claude Sonnet | Police, Lawyer, monthly chronicle |
| GPT-4o | Most agents (builders, explorers, teachers, healers, etc.) |
| Groq / Llama 3.3 | Merchants and messengers (free inference) |
| PostgreSQL | All persistent state — balances, transactions, cases, stories, assets |
| Qdrant | Per-agent private vector memory |
| Redis | Agent-to-agent message inboxes |
| FastAPI + WebSocket | Dashboard server |
| Python 3.12 | All simulation code |
| Phaser.js (Stage 6) | 2D top-down visual city in browser |

---

## Where We Start (Stage 1, First Task)

Build `src/city/event_log.py` and write `src/migrations/004_event_log.sql`.

The event_log table is the foundation. Every action in behaviors.py needs to call `log_event()` after it executes. Every crime, every build, every healing, every message — logged with initial visibility PRIVATE, then promoted as witnesses emerge and reports get filed.

After that: modify each behavior in `behaviors.py` to call `log_event()`. That's Stage 1 done.

---

## Notes for Claude in Future Sessions

- Do not add scripted drama arcs. All outcomes emerge from agent decisions.
- The Messenger LLM must ONLY see PUBLIC events. Enforce this strictly.
- The corrupt cop's bribe_susceptibility is NEVER shown in the dashboard or logs. It's a hidden DB field.
- Police investigation prompts must ONLY include evidence that exists in the DB — no god-view.
- When adding new villain behaviors, ask: does this leave evidence? What state does that evidence start at? Who could witness it?
- The visual city (Stage 6) uses Phaser.js in the browser — no external game engine.
- Build order is strict: Stage 1 → 2 → 3 → 4 → 5 → 6. Each depends on the previous.
