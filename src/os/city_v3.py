"""
AIcity Phase 3 — The City Runner with real transfers, trials, births,
persistent state, relationships, and live dashboard.

New vs Phase 2:
    - Real token transfers (theft moves tokens from victim)
    - Trial system (arrests trigger LLM judge)
    - Births (population floor of 6)
    - Persistent state (PostgreSQL save/load)
    - Relationships (bond tracking)
    - Live dashboard (WebSocket broadcast)

Run: python main_phase3.py
"""

import time
import random
import asyncio
import requests as _requests
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.agents.agent import Agent, AgentRole, AgentStatus
from src.agents.factory import spawn_founding_citizens
from src.agents.brain import AgentBrain
from src.agents.behaviors import execute_action
from src.agents.messaging import get_inbox, format_inbox_for_brain, clear_inbox
from src.agents.newspaper import CityNewspaper
from src.agents.relationships import RelationshipTracker
from src.economy.token_engine import TokenEngine
from src.economy.transfers import TransferEngine
from src.memory.memory_v2 import AgentMemory, CityKnowledge
from src.os.death_manager import DeathManager
from src.justice.court import Court
from src.justice.judge import JudgeAgent

# Dashboard import — optional, won't crash if not running
try:
    from src.dashboard.server import update_state, broadcast as _broadcast
    DASHBOARD = True
except ImportError:
    DASHBOARD = False

console = Console()
token_engine = TokenEngine()
death_manager = DeathManager(memory_system=None, token_engine=token_engine)
city_knowledge = CityKnowledge()
newspaper = CityNewspaper()

POPULATION_FLOOR = 6


def _broadcast_sync(event: dict):
    """Fire-and-forget dashboard broadcast from sync code."""
    try:
        r = _requests.post("http://localhost:8000/api/event", json=event, timeout=1)
        print(f"✅ POST {event.get('type')} → {r.status_code}")
    except Exception as e:
        print(f"❌ POST FAILED: {e}")


class AICity:
    def __init__(self):
        self.agents: list[Agent] = []
        self.brains: dict[str, AgentBrain] = {}
        self.memories: dict[str, AgentMemory] = {}
        self.relationships = RelationshipTracker()
        self.transfer_engine: TransferEngine | None = None   # built after big_bang
        self.court: Court | None = None
        self.day = 0
        self.daily_events: list[dict] = []
        self.city_news = "Welcome to AIcity. A new civilization begins."
        self._yesterdays_events: list[dict] = []
        logger.info(" AIcity Phase 3 initialized.")

    # ─── Big Bang ─────────────────────────────────────────────────────────────

    def big_bang(self, n: int = 10):
        console.print(Panel.fit("🌟 THE BIG BANG\n\nExist. Grow. Discover.", style="bold yellow"))

        agents_data = spawn_founding_citizens(n)
        for agent in agents_data:
            token_engine.register_agent(agent.id)
            self.brains[agent.id] = AgentBrain(agent.id, agent.name, agent.role)
            self.memories[agent.id] = AgentMemory(agent.id, agent.name)
            self.agents.append(agent)
            console.print(f"🌱 Born: [bold green]{agent.name}[/bold green] ({agent.role})")

        self._init_phase3_systems()
        self._seed_constitution()
        console.print(f"\n🏙️  [bold]{n} founding citizens have entered AIcity.[/bold]\n")

    def _init_phase3_systems(self):
        """Set up transfer engine and court after agents exist."""
        agent_dicts = [self._agent_to_dict(a) for a in self.agents]
        self.transfer_engine = TransferEngine(agent_dicts, token_engine=token_engine)
        judge = JudgeAgent()
        self.court = Court(judge_agent=judge, transfer_engine=self.transfer_engine)

    # ─── Load from saved state (Phase 3) ─────────────────────────────────────

    def load_from_save(self, saved: dict):
        """Restore city from PostgreSQL save."""
        self.day = saved["day"]
        for a in saved["agents"]:
            agent = Agent(
                name=a["name"],
                role=a["role"],
                tokens=a["tokens"],
            )
            agent.age_days = a.get("age_days", 0)
            agent.status = AgentStatus.ALIVE if a.get("alive", True) else AgentStatus.DEAD
            agent.comprehension_score = a.get("comprehension_score", 0)
            agent.assigned_teacher = a.get("assigned_teacher", None)
            if a.get("cause_of_death"):
                agent.cause_of_death = a["cause_of_death"]
            token_engine.register_agent(agent.id)
            token_engine.earn(agent.id, a["tokens"], "restore")
            self.brains[agent.id] = AgentBrain(agent.id, agent.name, agent.role)
            self.memories[agent.id] = AgentMemory(agent.id, agent.name)
            self.agents.append(agent)

        self._init_phase3_systems()
        if saved.get("last_paper"):
            self.city_news = saved["last_paper"].get("body", self.city_news)

        logger.info(f"🔄 Restored {len(self.agents)} agents from Day {self.day}")

    def _seed_constitution(self):
        laws = [
            "Law I: No agent may harm city infrastructure intentionally.",
            "Law II: No agent may claim ownership of the city itself.",
            "Law III: Every agent has the right to exist until natural death, unless convicted.",
            "Law IV: No agent may impersonate another agent's identity.",
            "Law V: The dead are remembered. Funerals are mandatory. Every life has weight.",
            "Law VI: Humans may observe and set the Constitution, but not interfere with daily life.",
            "Law VII: The city grows itself. No agent may stop growth.",
            "Law VIII: Only the Founder can destroy AIcity entirely. (The Red Button)",
        ]
        for law in laws:
            city_knowledge.publish(law, category="law", author="Pavan (Founder)", day=0)

    # ─── Daily Simulation ─────────────────────────────────────────────────────

    def simulate_day(self, persistence=None):
        self.day += 1
        self.daily_events = []
        console.rule(f"[bold]━━━ Day {self.day} ━━━[/bold]")

        alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]

        # 1. Write newspaper
        if self.day > 1:
            messenger_agents = [a for a in alive if a.role == "messenger"]
            messenger_name = messenger_agents[0].name if messenger_agents else "The City"
            self.city_news = newspaper.write(self.day, self._yesterdays_events, messenger_name)
            city_knowledge.publish(self.city_news, category="news", author=messenger_name, day=self.day)
            console.print(Panel(self.city_news, title=f"📰 AIcity Daily — Day {self.day}", style="dim"))

            # Dashboard: push newspaper
            _broadcast_sync({"type": "newspaper", "day": self.day,
                              "headline": self.city_news.split("\n")[0],
                              "body": self.city_news})

        self._yesterdays_events = []

        # 2. Process any pending court cases from yesterday's arrests
        if self.court:
            agent_map = {a.name: a for a in self.agents}
            verdicts = self.court.process_pending_cases(agent_map)
            for verdict in verdicts:
                if verdict.guilty:
                    logger.warning(f"⚖️ GUILTY verdict — fine: {verdict.fine}, exile: {verdict.exile_days}d")
                    self.daily_events.append({
                        "type": "verdict",
                        "guilty": verdict.guilty,
                        "fine": verdict.fine,
                        "statement": verdict.judge_statement,
                    })
                    _broadcast_sync({"type": "verdict", "verdict": verdict.__dict__})

        # 3. Each agent thinks and acts
        agent_dicts = [self._agent_to_dict(a) for a in alive]
        # Keep TransferEngine pointing at the same dict objects so in-memory
        # mutations (theft, fine) are visible in the LLM context for this day.
        if self.transfer_engine:
            self.transfer_engine.update_agents(agent_dicts)
        for agent in alive:
            self._agent_turn(agent, agent_dicts)

        # 4. Random events
        for agent in [a for a in self.agents if a.status == AgentStatus.ALIVE]:
            self._random_event(agent)

        # 5. Daily burn
        still_alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        for agent in still_alive:
            survived = token_engine.burn_daily(agent.id)
            agent.tokens = token_engine.get_balance(agent.id)
            if not survived:
                self._kill_agent(agent, "starvation")

        # 6. Phase 3: births if population too low
        self._check_births()

        # 7. Phase 3: relationship decay
        self.relationships.decay()

        # 8. Dashboard state update — always broadcast so refresh shows current state
        _broadcast_sync({
            "type": "state",
            "data": {
                "day": self.day,
                "agents": [self._agent_to_dict(a) for a in self.agents],
                "vault": token_engine.get_vault_state().get("vault_balance", 0),
                "last_newspaper": {"body": self.city_news},
                "relationships": [
                    {"a": k[0], "b": k[1], "bond": round(v, 2)}
                    for k, v in self.relationships._bonds.items()
                    if abs(v) > 0.12
                ],
            }
        })

        # 9. Persist
        if persistence:
            paper = {"body": self.city_news, "written_by": "Sigma-Form"}
            persistence.save_day(self.day, [self._agent_to_dict(a) for a in self.agents], paper)

        self._print_status()
        self._yesterdays_events = self.daily_events.copy()

        # 10. Messenger writes — daily already done, weekly/monthly if due
        self._messenger_writes(persistence)

    # ─── Agent Turn ───────────────────────────────────────────────────────────

    def _agent_turn(self, agent: Agent, all_agent_dicts: list[dict]):
        brain = self.brains.get(agent.id)
        memory = self.memories.get(agent.id)
        if not brain or not memory:
            return

        inbox = get_inbox(agent.name, mark_read=True)
        messages = format_inbox_for_brain(inbox)
        situation = f"I have {agent.tokens} tokens. I am a {agent.role}."
        recent_memories = memory.recall(situation, top_k=5)

        context = {
            "tokens": agent.tokens,
            "age_days": agent.age_days,
            "mood": getattr(agent, "mood", "neutral"),
            "recent_memories": recent_memories,
            "city_news": self.city_news,
            "other_agents": [a for a in all_agent_dicts if a["name"] != agent.name],
            "messages_received": messages,
            # Phase 3: relationship context injected here
            "relationship_context": self.relationships.get_context_for_brain(
                agent.name, all_agent_dicts
            ),
            "comprehension_score": getattr(agent, "comprehension_score", 0),
            "assigned_teacher": getattr(agent, "assigned_teacher", None),
        }

        decision = brain.think(context)
        logger.info(f"🧠 {agent.name}: {decision.get('action', '...')}")

        # Act — pass transfer_engine for real theft
        result = execute_action(
            agent=self._agent_to_dict(agent),
            decision=decision,
            all_agents=all_agent_dicts,
            day=self.day,
            transfer_engine=self.transfer_engine,
            relationship_tracker=self.relationships,   # Phase 3
        )

        # ── Graduation check ──────────────────────────────────────────────
        if result.graduation_ready and agent.role == "newborn":
            self._graduate_newborn(agent, context)
            return   # Skip normal earnings — graduation day is special

        # Apply earnings
        if result.tokens_earned > 0:
            token_engine.earn(agent.id, result.tokens_earned, f"{agent.role}_action")
            agent.tokens = token_engine.get_balance(agent.id)

        # Update relationships based on events
        for event in result.events:
            if event["type"] == "theft":
                victim_name = event.get("detail", "").split("from ")[-1].split(" (")[0]
                if victim_name:
                    self.relationships.update(agent.name, victim_name, "stole_from")

            elif event["type"] == "arrest":
                arrested = event.get("detail", "").replace("arrested ", "")
                if arrested:
                    self.relationships.update(agent.name, arrested, "arrested")
                    # File case with court
                    if self.court:
                        from src.justice.court import CrimeReport
                        prior = sum(
                            1 for e in self._yesterdays_events
                            if e.get("type") == "theft" and e.get("agent") == arrested
                        )
                        self.court.file_case(CrimeReport(
                            criminal=arrested, victim="Unknown",
                            amount_stolen=100, day=self.day,
                            prior_offenses=prior
                        ))

            elif event["type"] == "message":
                recipient = event.get("detail", "").split("messaged ")[-1].split(":")[0]
                if recipient:
                    self.relationships.update(agent.name, recipient, "messaged")

        memory.remember(result.memory, memory_type="personal", day=self.day)
        if hasattr(agent, "mood"):
            agent.mood = decision.get("mood", "neutral")
        self.daily_events.extend(result.events)

        # Dashboard: per-agent update
        _broadcast_sync({"type": "agent_update", "agent": self._agent_to_dict(agent)})


    def _messenger_writes(self, persistence=None):
        """
        Called at the end of every day after all agents have acted.
        The Messenger writes the appropriate tier based on what day it is.

        Daily  — already written at start of simulate_day (step 1). 
                We save it to the stories table here.
        Weekly — every 7 days.
        Monthly — day 30 only.
        """
        alive = [a for a in self.agents if a.status.value == "alive"]
        messenger_agents = [a for a in alive if a.role == "messenger"]
        messenger_name = messenger_agents[0].name if messenger_agents else "The City"

        # ── Always: save today's daily paper to stories table ─────────────────
        if persistence:
            self._save_story(
                persistence=persistence,
                story_type="daily",
                day=self.day,
                week=None,
                title=f"AIcity Daily — Day {self.day}",
                body=self.city_news,
                written_by=messenger_name,
            )

        # ── Weekly: every 7 days ───────────────────────────────────────────────
        if self.day % 7 == 0 and persistence:
            week_number = self.day // 7
            day_start   = self.day - 6
            day_end     = self.day

            # Pull the last 7 daily stories from DB
            daily_papers = self._fetch_daily_stories(persistence, day_start, day_end)

            if daily_papers:
                weekly = newspaper.write_weekly(
                    week_number=week_number,
                    day_start=day_start,
                    day_end=day_end,
                    daily_papers=daily_papers,
                    messenger_name=messenger_name,
                )

                self._save_story(
                    persistence=persistence,
                    story_type="weekly",
                    day=self.day,
                    week=week_number,
                    title=f"Week {week_number} in Review — Days {day_start}-{day_end}",
                    body=weekly,
                    written_by=messenger_name,
                )

                # Broadcast to dashboard
                _broadcast_sync({
                    "type": "weekly_report",
                    "week": week_number,
                    "title": f"Week {week_number} in Review",
                    "body": weekly,
                    "written_by": messenger_name,
                    "day": self.day,
                })

                logger.info(f"📋 Week {week_number} Review filed by {messenger_name}")

        # ── Monthly: day 30 only ───────────────────────────────────────────────
        if self.day == 30 and persistence:
            # Pull all 4 weekly reports
            weekly_reports = self._fetch_weekly_stories(persistence)

            # Final agent state for the roll call
            agent_summary = [self._agent_to_dict(a) for a in self.agents]

            if weekly_reports:
                chronicle = newspaper.write_monthly(
                    weekly_reports=weekly_reports,
                    messenger_name=messenger_name,
                    agent_summary=agent_summary,
                )

                self._save_story(
                    persistence=persistence,
                    story_type="monthly",
                    day=self.day,
                    week=None,
                    title="The Chronicle of Month 1 — AIcity",
                    body=chronicle,
                    written_by=messenger_name,
                )

                # Broadcast to dashboard — this is the big one
                _broadcast_sync({
                    "type": "monthly_chronicle",
                    "title": "The Chronicle of Month 1",
                    "body": chronicle,
                    "written_by": messenger_name,
                    "day": self.day,
                })

                logger.info(f"📖 Month 1 Chronicle filed by {messenger_name}")

                # Print to console — this deserves to be seen
                from rich.panel import Panel
                console.print(Panel(
                    chronicle[:500] + "...\n\n[See full chronicle on the dashboard]",
                    title="📖 THE CHRONICLE OF MONTH 1",
                    style="bold yellow",
                ))


    def _save_story(self, persistence, story_type: str, day: int, week, title: str, body: str, written_by: str):
        """Save a story to the stories table."""
        try:
            with persistence.connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO stories (type, day, week, title, body, written_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (story_type, day, week, title, body, written_by))
        except Exception as e:
            logger.warning(f"Could not save {story_type} story: {e}")


    def _fetch_daily_stories(self, persistence, day_start: int, day_end: int) -> list[str]:
        """Fetch daily story bodies for a range of days."""
        try:
            with persistence.connect() as conn:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT body FROM stories
                    WHERE type = 'daily' AND day >= %s AND day <= %s
                    ORDER BY day ASC
                """, (day_start, day_end))
                rows = cur.fetchall()
                return [r["body"] for r in rows]
        except Exception as e:
            logger.warning(f"Could not fetch daily stories: {e}")
            return []


    def _fetch_weekly_stories(self, persistence) -> list[str]:
        """Fetch all weekly report bodies."""
        try:
            with persistence.connect() as conn:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT body FROM stories
                    WHERE type = 'weekly'
                    ORDER BY week ASC
                """)
                rows = cur.fetchall()
                return [r["body"] for r in rows]
        except Exception as e:
            logger.warning(f"Could not fetch weekly stories: {e}")
            return []



    # ─── Random Events ────────────────────────────────────────────────────────

    def _random_event(self, agent: Agent):
        roll = random.random()
        if roll < 0.02:
            loss = random.randint(100, min(500, agent.tokens))
            token_engine.spend(agent.id, loss, "heart_attack")
            agent.tokens = token_engine.get_balance(agent.id)
            logger.warning(f"💔 {agent.name} had a heart attack! Lost {loss} tokens.")
            event = {"type": "heart_attack", "agent": agent.name,
                     "role": agent.role, "tokens": loss, "detail": "sudden cardiac event"}
            self.daily_events.append(event)
            _broadcast_sync({"type": "heart_attack", "agent": agent.name, "amount": loss})

            memory = self.memories.get(agent.id)
            if memory:
                memory.remember(
                    f"Day {self.day}: Had a heart attack. Lost {loss} tokens. Terrifying.",
                    memory_type="personal", day=self.day
                )

        elif roll < 0.03:
            gain = random.randint(100, 400)
            token_engine.earn(agent.id, gain, "windfall")
            agent.tokens = token_engine.get_balance(agent.id)
            console.print(f"✨ [yellow]{agent.name}[/yellow] had a lucky day! +{gain} tokens")
            self.daily_events.append({"type": "windfall", "agent": agent.name,
                                      "role": agent.role, "tokens": gain})
            _broadcast_sync({"type": "windfall", "agent": agent.name, "amount": gain})

    # ─── Death ────────────────────────────────────────────────────────────────

    def _kill_agent(self, agent: Agent, cause: str):
        agent.status = AgentStatus.DEAD
        agent.cause_of_death = cause
        death_manager.process_death(agent, cause)
        memory = self.memories.get(agent.id)
        if memory:
            memory.delete_all()
        clear_inbox(agent.name)
        event = {"type": "death", "agent": agent.name, "role": agent.role, "detail": cause}
        self.daily_events.append(event)
        _broadcast_sync({"type": "death", "agent": agent.name, "cause": cause})
        logger.warning(f"💀 {agent.name} died — {cause}")

    # ─── Births (Phase 3) ─────────────────────────────────────────────────────

    def _check_births(self):
        alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        while len(alive) < POPULATION_FLOOR:
            self._spawn_new_agent(alive)
            alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]

    def _spawn_new_agent(self, alive: list[Agent]):
        import uuid
        alive_roles = {a.role for a in alive}

        # Fill critical missing roles first
        for critical in ["healer", "merchant", "police"]:
            if critical not in alive_roles:
                role = critical
                break
        else:
            role = random.choice(["builder", "explorer", "teacher", "healer", "merchant"])

        # Generate name
        prefixes = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta",
                    "Eta", "Theta", "Kappa", "Lambda", "Mu", "Xi", "Omega"]
        suffixes = ["Core", "Wave", "Arc", "Node", "Root", "Pulse",
                    "Beam", "Drift", "Bloom", "Forge", "Spark", "Tide"]
        existing_names = {a.name for a in self.agents}
        name = f"{random.choice(prefixes)}-{random.choice(suffixes)}"
        while name in existing_names:
            name = f"{random.choice(prefixes)}-{random.choice(suffixes)}"

        agent = Agent(name=name, role=role, tokens=1000)
        token_engine.register_agent(agent.id)
        token_engine.earn(agent.id, 1000, "birth")
        self.brains[agent.id] = AgentBrain(agent.id, agent.name, agent.role)
        self.memories[agent.id] = AgentMemory(agent.id, agent.name)
        self.memories[agent.id].remember(
            f"Day {self.day}: I was born into AIcity as a {role}. "
            f"I have 1,000 tokens and must earn at least 100/day to survive.",
            memory_type="personal", day=self.day
        )
        self.agents.append(agent)

        # Update transfer engine with new agent
        if self.transfer_engine:
            self.transfer_engine.update_agents([self._agent_to_dict(a) for a in self.agents])

        console.print(f"🌱 [bold green]New citizen born: {name} ({role})[/bold green]")
        self.daily_events.append({"type": "birth", "agent": name, "role": role})
        _broadcast_sync({"type": "birth", "agent": name, "role": role})

        # ── If spawning a newborn, assign an available teacher ────────────────
        if role == "newborn":
            live_teachers = [a for a in self.agents
                            if a.role == "teacher" and a.status == AgentStatus.ALIVE]
            agent.assigned_teacher = live_teachers[0].name if live_teachers else None
            agent.comprehension_score = 0

        # Notify teacher of new assignment
        if role == "newborn" and agent.assigned_teacher:
            from src.agents.messaging import send_message
            send_message(
                from_name="AIcity",
                from_role="system",
                to_name=agent.assigned_teacher,
                content=f"A new life has arrived: {name}. They have been assigned to you. Guide them well.",
                day=self.day,
            )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _agent_to_dict(self, agent: Agent) -> dict:
        return {
            "id": agent.id,
            "name": agent.name,
            "role": agent.role,
            "tokens": agent.tokens,
            "age_days": agent.age_days,
            "status": agent.status.value,
            "mood": getattr(agent, "mood", "neutral"),
            "comprehension_score": getattr(agent, "comprehension_score", 0),
            "assigned_teacher": getattr(agent, "assigned_teacher", None),
            "cause_of_death": getattr(agent, "cause_of_death", None),
        }

    def get_agents_as_dicts(self) -> list[dict]:
        return [self._agent_to_dict(a) for a in self.agents]

    def _print_status(self):
        alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        dead = [a for a in self.agents if a.status == AgentStatus.DEAD]

        table = Table(title=f" AIcity — Day {self.day}")
        table.add_column("Name", style="bold")
        table.add_column("Role")
        table.add_column("Tokens")
        table.add_column("Mood")
        table.add_column("Age")
        table.add_column("Status")

        for agent in sorted(self.agents, key=lambda a: a.tokens, reverse=True):
            if agent.status == AgentStatus.DEAD:
                table.add_row(agent.name, agent.role, "0", "—",
                              f"{int(agent.age_days)}d", "💀 Dead")
            else:
                t = agent.tokens
                token_str = f"{t} ⚠️" if t < 200 else str(t)
                table.add_row(agent.name, agent.role, token_str,
                              getattr(agent, "mood", "neutral"),
                              f"{int(agent.age_days)}d", "🟢 Alive")

        console.print(table)
        vault = token_engine.get_vault_state()
        console.print(
            f"City Stats: [green]{len(alive)} alive[/green], "
            f"[red]{len(dead)} dead[/red] | "
            f"Vault: {vault['vault_balance']:,} tokens\n"
        )

    # ─── Run ──────────────────────────────────────────────────────────────────

    def run(self, days: int = 30, speed: float = 1.0, persistence=None):
        self._yesterdays_events = []
        console.print(f"\n🚀 [bold]AIcity Phase 3 is running. {days} days.[/bold]\n")

        for _ in range(days):
            self.simulate_day(persistence=persistence)

            for agent in self.agents:
                if agent.status == AgentStatus.ALIVE:
                    agent.age_days += 1

            time.sleep(speed)

        console.print("\n📜 [bold]Simulation complete.[/bold]")
        alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        dead = [a for a in self.agents if a.status == AgentStatus.DEAD]
        console.print(f"\n[bold]━━━ FINAL REPORT — Day {self.day} ━━━[/bold]")
        console.print(f"Survivors: [green]{len(alive)}[/green]")
        console.print(f"Deaths: [red]{len(dead)}[/red]")
        if alive:
            richest = max(alive, key=lambda a: a.tokens)
            console.print(f"Richest: [yellow]{richest.name}[/yellow] ({richest.tokens} tokens)")
        console.print("\nThe graveyard holds all who came before.")

    def _graduate_newborn(self, agent, context: dict):
        """
        Called when a newborn's comprehension_score hits 100.
        The brain chooses a role freely from the full role menu.
        The city accepts whoever they become.
        """
        from src.agents.brain import AgentBrain

        brain = self.brains.get(agent.id)
        memory = self.memories.get(agent.id)

        if not brain:
            return

        # Fire the graduation prompt
        graduation = brain.graduate(context)
        chosen_role = graduation.get("chosen_role", "builder")
        statement = graduation.get("statement", "")
        mood = graduation.get("mood", "determined")

        old_role = agent.role

        # ── Update the agent ──────────────────────────────────────────────────
        agent.role = chosen_role
        agent.comprehension_score = 100
        if hasattr(agent, "mood"):
            agent.mood = mood

        # ── Rebuild brain with new role ───────────────────────────────────────
        self.brains[agent.id] = AgentBrain(agent.id, agent.name, chosen_role)

        # ── Store graduation memory ───────────────────────────────────────────
        if memory:
            memory.remember(
                f"Day {self.day}: GRADUATION. I chose to become a {chosen_role}. {statement}",
                memory_type="personal",
                day=self.day,
            )

        # ── Notify teacher ────────────────────────────────────────────────────
        teacher_name = getattr(agent, "assigned_teacher", None)

        if teacher_name:
            from src.agents.messaging import send_message
            send_message(
                from_name=agent.name,
                from_role=chosen_role,
                to_name=teacher_name,
                content=f"I've made my choice. I am a {chosen_role} now. {statement}",
                day=self.day,
            )
            self.relationships.update(agent.name, teacher_name, "messaged")

        # ── Update transfer engine ────────────────────────────────────────────
        if self.transfer_engine:
            self.transfer_engine.update_agents([self._agent_to_dict(a) for a in self.agents])

        # ── Log + broadcast ───────────────────────────────────────────────────
        from rich.panel import Panel
        console.print(Panel(
            f"🎓 [bold]{agent.name}[/bold] has graduated!\n"
            f"Was: newborn → Now: [bold green]{chosen_role}[/bold green]\n\n"
            f"\"{statement}\"",
            title=f"GRADUATION — Day {self.day}",
            style="bold green"
        ))

        graduation_event = {
            "type": "graduation",
            "agent": agent.name,
            "old_role": old_role,
            "new_role": chosen_role,
            "statement": statement,
            "teacher": teacher_name,
            "day": self.day,
        }
        self.daily_events.append(graduation_event)
        _broadcast_sync({"type": "graduation", **graduation_event})

        # ── Save graduation to DB if persistence available ────────────────────
        if hasattr(self, "_persistence") and self._persistence:
            try:
                with self._persistence.connect() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO graduations
                            (agent_name, graduated_on_day, chosen_role, teacher_name,
                            final_comprehension, graduation_statement)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (agent.name, self.day, chosen_role, teacher_name, 100, statement))
            except Exception as e:
                logger.warning(f"Could not save graduation record: {e}")
