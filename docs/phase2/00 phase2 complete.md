# Phase 2 — Complete Build Documentation

**Status:** ✅ Complete
**Built:** February 2026

---

## What We Built

Phase 2 gives every agent a real LLM brain. No more random numbers.

| File | Purpose |
|------|---------|
| `src/agents/brain.py` | LLM decision engine — agents think before acting |
| `src/agents/messaging.py` | Inbox/outbox system — agents talk to each other |
| `src/agents/newspaper.py` | Daily newspaper written by the Messenger |
| `src/agents/behaviors.py` | Role-specific behaviors — how each role earns |
| `src/memory/memory_v2.py` | Semantic memory with embeddings |
| `src/os/city_v2.py` | Full Phase 2 city runner |
| `main_phase2.py` | Entry point |

---

## Step 1 — The Agent Brain (`brain.py`)

Every agent gets an `AgentBrain`. Each morning:

1. Agent receives context: tokens, age, mood, city news, inbox, nearby agents
2. Brain sends context to LLM
3. LLM returns a JSON decision: action, reasoning, who to message, mood
4. End of day: agent reflects and writes a personal memory

**LLM routing:**
- Police, Lawyers → Claude Sonnet (best reasoning)
- Builders, Explorers, Healers, Teachers → GPT-4o
- Merchants, Messengers, Newborns → Llama 3 (via Ollama)
- Thieves → GPT-4o (Mistral later)

---

## Step 2 — Messaging System (`messaging.py`)

Agents now have real inboxes. Built on Redis with 3-day TTL.

- `send_message()` — deliver a message to any agent's inbox
- `get_inbox()` — read all messages
- `broadcast()` — Messenger sends city-wide announcements
- `format_inbox_for_brain()` — formats messages for the brain prompt
- Messages expire after 3 days automatically

---

## Step 3 — Semantic Memory (`memory_v2.py`)

Memories are now embedded with `text-embedding-3-small` and stored in Qdrant.

Instead of "last 5 memories", agents recall "most relevant memories to today's situation." A builder with low tokens will automatically recall memories about survival and hard work — not memories about windfalls.

- `remember()` — embed and store any memory
- `recall()` — semantic search across personal memories
- `recall_about()` — what do I know about a specific agent?
- `CityKnowledge` — shared city-wide knowledge (laws, news, discoveries)

---

## Step 4 — The Newspaper (`newspaper.py`)

The Messenger writes the AIcity Daily every morning using GPT-4o. It gets a list of yesterday's events and generates a vivid short newspaper. Every agent reads this before deciding what to do.

Published to the shared city knowledge base so it's permanently searchable.

---

## Step 5 — Role Behaviors (`behaviors.py`)

Each role now has a real behavior function. The brain's decision affects the outcome:

- **Builder**: Works harder = earns more. Mentions "desperate" or "overtime" = 40% bonus
- **Explorer**: High variance. 15% chance of massive discovery, 15% chance of nothing
- **Merchant**: Earns more when rich agents are around to trade with
- **Police**: 25% chance to catch a Thief when patrolling. Arrest = +200 token bonus
- **Teacher**: Earns more when there are students (Newborns, Builders) in the city
- **Healer**: Earns more when critical agents need help. Automatically messages them
- **Messenger**: Network bonus — more alive agents = more to deliver
- **Thief**: 45% success rate when stealing. Targets the richest agent. Has a code (never steals from Newborns)
- **Newborn**: Automatically messages the Teacher when tokens drop below 400

---

## Step 6 — City Runner (`city_v2.py`)

Daily cycle:
1. Messenger writes the newspaper (from yesterday's events)
2. Each agent reads inbox + recalls memories + brain thinks
3. Agent acts (role behavior executes)
4. Random events (heart attacks, windfalls)
5. Daily burn — 100 tokens cost of existence
6. Deaths processed with funerals
7. Status table printed

---

## Running Phase 2

```bash
# Make sure Docker is running
docker-compose up -d

# Make sure .env has your API keys
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key

# Run
python main_phase2.py
```

---

## Git Commits for Phase 2

```bash
git add .
git commit -m "feat(phase2): complete Phase 2 — LLM brains, messaging, semantic memory, newspaper, role behaviors"
git push origin main
```

---

## What's Different from Phase 1

| Feature | Phase 1 | Phase 2 |
|---------|---------|---------|
| Earnings | Random number | LLM decides → behavior executes |
| Memory | None | Semantic embeddings in Qdrant |
| Communication | None | Redis inbox/outbox |
| City news | None | GPT-4o newspaper every morning |
| Thief behavior | Random steal | Targets richest, 45% success rate |
| Police behavior | Random patrol | Actually tries to catch Thieves |
| Healer behavior | Random heal | Messages critical agents |
| Newborn behavior | Random earn | Asks Teacher for help automatically |
| Agent mood | None | Tracked, affects decisions |

---

## What Phase 3 Will Add

- Real token transfers between agents (Healers can donate, Thieves can steal real tokens)
- Property ownership — agents can buy and own things
- Marriage and family
- Seasons and weather affecting earnings
- Trial system — Thief arrested → Lawyer defends → Judge rules