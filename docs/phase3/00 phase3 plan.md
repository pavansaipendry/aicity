# 🏙️ AIcity — Phase 3 Plan

> **Status:** Planning  
> **Follows:** Phase 2 — LLM Brains, Messaging, Memory, Newspaper  
> **Goal:** Transform AIcity from a narrative simulation into a true emergent economy with real consequences.

---

## What Phase 2 Proved

Phase 2 demonstrated that:
- LLM brains + shared memory + daily newspaper = coherent emergent narratives
- Agents form relationships and react to each other over time
- Death creates genuine drama
- The merchant role dominates; newborns and thieves are structurally vulnerable

**The core gap:** Nothing has real bilateral consequences. The thief steals but the victim doesn't lose tokens. The police arrest but there's no trial. The city resets every run.

Phase 3 fixes this.

---

## Phase 3 Features

| # | Feature | Priority | Complexity |
|---|---------|----------|------------|
| 1 | [Real Token Transfers](./01_real_transfers.md) | 🔴 Critical | Low |
| 2 | [Trial System](./02_trial_system.md) | 🔴 Critical | Medium |
| 3 | [Births & Population](./03_births.md) | 🟡 High | Low |
| 4 | [Persistent State](./04_persistent_state.md) | 🟡 High | High |
| 5 | [Relationships](./05_relationships.md) | 🟢 Medium | Medium |
| 6 | [Live Dashboard](./06_dashboard.md) | 🟢 Medium | Medium |

---

## Phase 3 Architecture

```
aicity/
├── src/
│   ├── os/
│   │   ├── city_v3.py          # New city runtime
│   │   └── city_v2.py          # Phase 2 (kept)
│   ├── economy/
│   │   ├── token_engine.py     # + real transfers
│   │   └── transfers.py        # NEW: bilateral transfers
│   ├── justice/
│   │   ├── court.py            # NEW: trial system
│   │   └── judge.py            # NEW: judge LLM agent
│   ├── agents/
│   │   ├── brain.py            # + relationship context
│   │   ├── relationships.py    # NEW: bond tracking
│   │   └── births.py           # NEW: agent spawning
│   ├── memory/
│   │   ├── memory_v2.py        # Phase 2 (kept)
│   │   └── persistence.py      # NEW: PostgreSQL state
│   └── dashboard/
│       ├── server.py           # NEW: FastAPI server
│       └── static/
│           └── index.html      # Live dashboard
├── main_phase3.py
└── docs/
    └── phase3/
        ├── 00_phase3_plan.md   ← you are here
        ├── 01_real_transfers.md
        ├── 02_trial_system.md
        ├── 03_births.md
        ├── 04_persistent_state.md
        ├── 05_relationships.md
        └── 06_dashboard.md
```

---

## Development Order

Build in this sequence — each feature unlocks the next:

```
1. Real Transfers    → economy has teeth
2. Trial System      → crime has consequences
3. Births            → city survives forever
4. Persistent State  → city survives restarts
5. Relationships     → agents have memory of each other
6. Dashboard         → humans can watch it all live
```

---

## Key Design Decisions

### Economy stays zero-sum (mostly)
Once real transfers are in, wealth can actually concentrate or distribute based on agent behavior. The vault remains the ultimate source, but agent-to-agent transfers create real stakes.

### Trials are LLM-powered
The judge is a real LLM agent — not a rule engine. It reads the case file, considers the evidence, and produces a verdict. Outcomes are unpredictable.

### Population floor: 6 agents
If population drops below 6, births are triggered automatically. City never goes extinct.

### PostgreSQL as single source of truth
All agent state, memory, relationships, and history persisted in Postgres. City can be stopped and resumed at any day with full fidelity.

---

## Phase 2 → Phase 3 Migration

| Component | Phase 2 | Phase 3 |
|-----------|---------|---------|
| Token stealing | Thief gains, victim unchanged | Thief gains, victim loses |
| Arrests | Police earns, thief notified | Police earns, triggers trial |
| Population | Fixed 10, can only shrink | Dynamic, new agents born |
| State | In-memory, resets on restart | PostgreSQL, survives restarts |
| Agent bonds | Implicit (messages only) | Explicit (bond strength tracked) |
| Viewing | Terminal only | Terminal + web dashboard |

---

*Phase 3 begins now. The city is alive — let's make it real.*