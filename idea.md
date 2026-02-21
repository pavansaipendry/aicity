# AIcity — Game Idea

## Core Concept

A city-building game where **AI agents live autonomously** and **players issue commands** to
shape the world — but the city has a life of its own that no one fully controls.

Think SimCity meets The Sims, except every citizen is a real LLM making real decisions.

---

## The Two Layers

### Layer 1 — The Player (you)
The player is essentially the **city mayor / god**.
You have a budget of tokens (bought with real money or earned in-game).
You spend them to issue commands:

| Command | Token cost | What happens |
|---------|-----------|--------------|
| "Build a hospital at row 20, col 45" | 500 tokens | A builder agent is assigned, construction begins |
| "Place a road from market to school" | 200 tokens | Builder lays road segments over N days |
| "Hire a new police officer" | 300 tokens | New police agent spawns |
| "Demolish the dark alley" | 150 tokens | Tile removed, zone cleared |
| "Move the market 10 tiles east" | 400 tokens | Market agents pack up, rebuild |
| "Declare this week a tax holiday" | 800 tokens | All agents earn +20% for 7 days |

The player sees everything from above — isometric view, real-time.

### Layer 2 — The Agents (not you)
The 10–50 AI agents live in the city **completely independently**.
They have their own goals, relationships, economies, and crimes.

- The **merchant** will open a second stall if business is good — you didn't ask.
- The **thief** will rob the merchant — you can't stop it directly.
- The **gang leader** will recruit the blackmailer — politics you didn't plan.
- The **builder** might refuse your order if they hate the police chief.
- The **healer** will rush to a cardiac victim without being told.

They respond to the city state, to each other, and to player commands — but they
are **not obedient**. A builder with low tokens might demand pay before starting
your project. A corrupt police officer might ignore the crime you reported.

---

## The Tension (why it's fun)

The game is interesting because **you don't have full control**.

You try to build a school near the residential zone. But the blackmailer lives there
and doesn't want it — she starts bribing the builder to slow construction.
You have to hire a second builder or pay a bribe yourself to get it done.

You order a road through the forest. The explorer has been mapping that forest for
5 days and considers it his territory. He might protest, slow-walk the work, or
just ignore your command.

The player is powerful (commands + budget) but the city has emergent politics.
The fun is in managing a city that has opinions about itself.

---

## Monetization

### Pay-to-play (player buys tokens)

| Pack | Price | Tokens | Best for |
|------|-------|--------|---------|
| Starter | $2 | 1,000 | Try it |
| Builder | $5 | 3,000 | Weekend session |
| Mayor | $15 | 12,000 | Serious play |
| Governor | $40 | 40,000 | Power users |

Tokens are the currency of influence. Every command costs tokens.
Free users can **watch** — the city runs itself 24/7 — but cannot issue commands.

### Spectator mode (free)
Anyone can open the browser and watch the city live.
You see:
- Agents walking around in real-time
- The newspaper written by the messenger each day
- Crime reports, court cases, births, deaths
- The economy (who's rich, who's broke)

This is free and shareable. Users share screenshots, clips, drama ("The thief just
robbed the merchant for the 4th day in a row and the corrupt cop did nothing").

Spectators who want to intervene → buy tokens → become players.

### Subscription (optional, $8/month)
- 500 bonus tokens/month
- "Advisor" tag visible to other spectators
- Access to a private command queue (commands execute overnight when server is quiet)
- City history: full replay of every day since founding

---

## Game Loop

```
Day starts
  → Agents wake up, move to work zones
  → Player issues commands (spend tokens)
  → Agents execute commands IF they agree (or if paid enough)
  → Agents also do their own thing simultaneously
  → Meetings, crimes, trades happen autonomously
  → Evening: results — who built what, who stole from whom
  → Newspaper written by Theo Fenn: headlines about today
  → Player sees what worked, what didn't, plans tomorrow
Day ends
```

One real-world day = ~30 in-game days (city runs 24/7 on the server).
Players log in, issue commands, log out. City continues while they're away.

---

## What makes it different from every other city builder

| Feature | Normal city builders | AIcity |
|---------|---------------------|--------|
| Citizens | Dumb NPCs following scripts | Real LLMs making real decisions |
| Construction | Instant on your command | Agents negotiate, debate, sometimes refuse |
| Crime | Random event popup | A real thief with a plan, a real cop who might be bribed |
| Newspaper | None | Written daily by an LLM journalist covering real events |
| Story | None | Emergent: gang wars, love stories, political scandals |
| Player control | Total | Influential but not absolute |
| Watch mode | No | Yes — live, free, shareable |

---

## Phase 1 (now — what we have)

- ✅ 10 autonomous AI agents running 24/7
- ✅ Isometric city view in browser
- ✅ Agents walk, build roads, plant trees
- ✅ Daily newspaper, relationships, crimes, court cases
- ✅ Economy (tokens, theft, taxes)

## Phase 2 (next — what to build for the game)

- [ ] Player command input UI (text box or click-on-map)
- [ ] Token wallet + Stripe payment integration
- [ ] Command queue system (player commands routed to relevant agents)
- [ ] Agent "opinion" system (will they accept the command?)
- [ ] Spectator feed (shareable live URL)
- [ ] More agents (20–50) so the city feels populated

## Phase 3 (product)

- [ ] Public launch
- [ ] Multiple cities running in parallel (each city is a separate game instance)
- [ ] Players can own buildings (permanent — survives resets)
- [ ] Inter-city trade (future)

---

## The Pitch (one paragraph)

> AIcity is a living city simulator where every citizen is powered by a real AI.
> You play as the mayor — you can build roads, hire workers, and pass laws — but
> the citizens have their own economy, crimes, relationships, and ambitions.
> Your commands cost tokens. Some agents will follow them. Some won't.
> The city runs 24 hours a day whether you're logged in or not.
> Watch it live for free. Shape it if you pay. Share the drama either way.
