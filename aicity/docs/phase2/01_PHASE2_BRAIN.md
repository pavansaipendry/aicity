# Step 1 — The Agent Brain

**What we built:** `src/agents/brain.py`
**Goal:** Replace random number simulation with real LLM decision-making.

---

## What It Does

Every agent now has a `AgentBrain`. Each morning of the simulation:

1. The agent receives context — their tokens, age, mood, city news, messages received, and what they know about other agents
2. The brain sends this to an LLM
3. The LLM responds with a JSON decision: what action to take, why, who to message, and what mood they're in
4. At end of day, the agent reflects and writes a personal memory

---

## LLM Assignment

| Role | Model | Reason |
|------|-------|--------|
| Police, Lawyer | Claude Sonnet | Best reasoning — needed for justice |
| Builder, Explorer, Healer, Teacher | GPT-4o | Fast, versatile |
| Merchant, Messenger, Newborn | Llama 3 (Ollama) | Free, scalable |
| Thief | GPT-4o (Mistral later) | Adversarial thinking |

---

## Key Design Decisions

**Why different models per role?**
Cost and character. A Newborn agent doesn't need Claude Sonnet — that's expensive and wasteful. A Police officer deciding whether to arrest someone needs the best reasoning available.

**Why JSON responses?**
Structured output is easier to parse and act on programmatically. The brain returns a clean dict every time.

**Why a fallback?**
LLMs fail. Rate limits happen. The simulation must keep running even if one agent's API call errors out. The `_default_decision()` method ensures the city never crashes due to an LLM failure.

**Why `reflect()`?**
Memories that are *written by the agent themselves* are richer than logs. "I spent the day building and earned 143 tokens" is boring. "I poured everything into the foundation today — if this structure stands, I'll finally have enough to breathe" is a memory worth reading.

---

## The Prompt Structure

Every agent gets a prompt with:
- Their current token count + danger level (CRITICAL / WARNING / STABLE / THRIVING)
- Today's city news (written by the Messenger)
- Their last 5 memories
- Messages they received from other agents
- A list of other citizens and their token counts

The danger level phrasing is intentional — agents respond differently when they see "⚠️ CRITICAL — You will die soon" vs "✅ THRIVING — Think bigger."

---

## What the Brain Returns

```json
{
    "action": "I take on an extra build contract, working through the night",
    "reasoning": "My tokens are critically low and I cannot afford another bad day",
    "message_to": "Omega-Pulse",
    "message": "I need work. Do you have anything that pays well?",
    "mood": "desperate"
}
```

---

## Git Commit

```bash
git add src/agents/brain.py
git commit -m "feat(phase2): add agent brain with LLM decision engine"
git push origin main
```