# AIcity — Master Development Log

> Every step. Every decision. Every reason why.

---

## Project Overview

**Name:** AIcity (OASAI — Operating System for Artificial Intelligence)
**Founded by:** Pavan
**Started:** February 2026
**Vision:** The first self-governing AI civilization. 1,000 agents that exist, grow, and discover — on their own terms.

---

## Development Phases

| Phase | Name | Status | Duration |
|-------|------|--------|----------|
| Phase 1 | The Skeleton | 🔄 In Progress | Month 1–2 |
| Phase 2 | The Citizens | ⏳ Pending | Month 3–4 |
| Phase 3 | The City | ⏳ Pending | Month 5–6 |
| Phase 4 | The Law | ⏳ Pending | Month 7–8 |
| Phase 5 | The World | ⏳ Pending | Month 9–10 |
| Phase 6 | The Public | ⏳ Pending | Month 11–12 |

---

## Phase 1 — The Skeleton

**Goal:** Build the core of OASAI. Agent spawning, token system, memory, and death. Test with 10 agents.

**Deliverables:**
- [ ] Project structure set up
- [ ] Agent class — the DNA of every agent
- [ ] Token engine — the economy's heartbeat
- [ ] Memory system — private and shared
- [ ] Death mechanism — starvation logic
- [ ] Agent lifecycle — born, lives, dies
- [ ] 10 test agents running simultaneously
- [ ] Basic logging — every action recorded

---

## Decision Log

Every important decision made during development is recorded here.

| Date | Decision | Reason |
|------|----------|--------|
| Feb 2026 | Use Python as primary language | Best ecosystem for AI, most agent frameworks are Python-native |
| Feb 2026 | Use LangGraph for OS layer | Best stateful agent management, handles complex lifecycles |
| Feb 2026 | Use Qdrant for long-term memory | Open source, fast, self-hostable |
| Feb 2026 | Use Redis for short-term memory | Industry standard for fast in-memory operations |
| Feb 2026 | Use PostgreSQL for token ledger | Immutable, reliable, battle-tested for financial records |
| Feb 2026 | Use Docker for agent containers | Each agent isolated, prevents cross-contamination |
| Feb 2026 | 1,000 token starting balance | Gives 10 days of life at 100 tokens/day burn rate |
| Feb 2026 | No internal war in v1.0 | Too complex for Phase 1, reserved for multi-city expansion |
| Feb 2026 | Politics unlocked at 80,000 agents | City needs maturity before it needs politics |
| Feb 2026 | Only Pavan holds the Red Button | One person responsible for what grows here |

---

## The Big Bang Words

> *Exist. Grow. Discover.*

These three words are hardcoded into every agent at birth. They are not instructions. They are instincts.

---

## Links

- [01_PHASE1_SETUP.md](./01_PHASE1_SETUP.md) — Environment setup
- [02_PHASE1_AGENT.md](./02_PHASE1_AGENT.md) — The Agent class
- [03_PHASE1_TOKENS.md](./03_PHASE1_TOKENS.md) — Token engine
- [04_PHASE1_MEMORY.md](./04_PHASE1_MEMORY.md) — Memory system
- [05_PHASE1_DEATH.md](./05_PHASE1_DEATH.md) — Death mechanism
- [06_PHASE1_TEST.md](./06_PHASE1_TEST.md) — Running 10 agents