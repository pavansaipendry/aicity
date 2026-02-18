"""
AIcity Phase 2 — The City Runner with LLM brains.

Every agent now thinks before acting. The Messenger writes a daily newspaper.
Agents send messages to each other. Memory is semantic. The city breathes.

Run: python main_phase2.py
"""

import time
import random
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from src.agents.agent import Agent, AgentRole, AgentStatus
from src.agents.factory import spawn_founding_citizens
from src.agents.brain import AgentBrain
from src.agents.behaviors import execute_action
from src.agents.messaging import get_inbox, format_inbox_for_brain, clear_inbox
from src.agents.newspaper import CityNewspaper
from src.economy.token_engine import TokenEngine
from src.memory.memory_v2 import AgentMemory, CityKnowledge
from src.os.death_manager import DeathManager

console = Console()
token_engine = TokenEngine()
death_manager = DeathManager(memory_system=None, token_engine=token_engine)
city_knowledge = CityKnowledge()
newspaper = CityNewspaper()


class AICity:
    def __init__(self):
        self.agents: list[Agent] = []
        self.brains: dict[str, AgentBrain] = {}       # agent_id → brain
        self.memories: dict[str, AgentMemory] = {}    # agent_id → memory
        self.day = 0
        self.daily_events: list[dict] = []
        self.city_news = "Welcome to AIcity. A new civilization begins."
        logger.info("🏙️  AIcity Phase 2 initialized.")

    # ─── Big Bang ─────────────────────────────────────────────────────────────

    def big_bang(self, n: int = 10):
        console.print(Panel.fit("🌟 THE BIG BANG\n\nExist. Grow. Discover.", style="bold yellow"))

        agents_data = spawn_founding_citizens(n)
        for agent in agents_data:
            # Register in economy
            token_engine.register_agent(agent.id)

            # Create brain
            self.brains[agent.id] = AgentBrain(agent.id, agent.name, agent.role)

            # Create memory
            self.memories[agent.id] = AgentMemory(agent.id, agent.name)

            self.agents.append(agent)
            console.print(f"🌱 Born: [bold green]{agent.name}[/bold green] ({agent.role})")

        # Seed city knowledge with the constitution
        self._seed_constitution()

        console.print(f"\n🏙️  [bold]{n} founding citizens have entered AIcity.[/bold]\n")

    def _seed_constitution(self):
        """Write the 8 Laws into city knowledge."""
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
        logger.info("📜 Constitution seeded into city knowledge.")

    # ─── Daily Simulation ──────────────────────────────────────────────────────

    def simulate_day(self):
        self.day += 1
        self.daily_events = []
        console.rule(f"[bold]━━━ Day {self.day} ━━━[/bold]")

        alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]

        # 1. Write the newspaper (before agents decide)
        if self.day > 1:
            messenger_agents = [a for a in alive if a.role == "messenger"]
            messenger_name = messenger_agents[0].name if messenger_agents else "The City"
            self.city_news = newspaper.write(self.day, self._yesterdays_events, messenger_name)

            # Publish to city knowledge
            city_knowledge.publish(
                self.city_news,
                category="news",
                author=messenger_name,
                day=self.day
            )
            console.print(Panel(self.city_news, title=f"📰 AIcity Daily — Day {self.day}", style="dim"))

        self._yesterdays_events = []

        # 2. Each agent thinks and acts
        agent_dicts = [self._agent_to_dict(a) for a in alive]

        for agent in alive:
            self._agent_turn(agent, agent_dicts)

        # 3. Random city events (heart attacks, windfalls)
        for agent in alive:
            self._random_event(agent)

        # 4. Daily burn — cost of existence
        still_alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        for agent in still_alive:
            survived = token_engine.burn_daily(agent.id)
            agent.tokens = token_engine.get_balance(agent.id)
            if not survived:
                self._kill_agent(agent, "starvation")

        # 5. Show status
        self._print_status()
        self._yesterdays_events = self.daily_events.copy()

    def _agent_turn(self, agent: Agent, all_agent_dicts: list[dict]):
        """One agent's full daily turn: read inbox, think, act, remember."""
        brain = self.brains.get(agent.id)
        memory = self.memories.get(agent.id)

        if not brain or not memory:
            return

        # Gather context for the brain
        inbox = get_inbox(agent.name, mark_read=True)
        messages = format_inbox_for_brain(inbox)

        # Recall relevant memories
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
        }

        # Think
        decision = brain.think(context)
        logger.info(f"🧠 {agent.name}: {decision.get('action', '...')}")

        # Act
        result = execute_action(
            agent=self._agent_to_dict(agent),
            decision=decision,
            all_agents=all_agent_dicts,
            day=self.day
        )

        # Apply earnings
        if result.tokens_earned > 0:
            token_engine.earn(agent.id, result.tokens_earned, f"{agent.role}_action")
            agent.tokens = token_engine.get_balance(agent.id)

        # Store memory
        memory.remember(result.memory, memory_type="personal", day=self.day)

        # Update mood
        if hasattr(agent, "mood"):
            agent.mood = decision.get("mood", "neutral")

        # Collect events for newspaper
        self.daily_events.extend(result.events)

    def _random_event(self, agent: Agent):
        """Heart attacks and windfalls still happen."""
        roll = random.random()
        if roll < 0.02:  # 2% heart attack
            loss = random.randint(100, min(500, agent.tokens))
            token_engine.spend(agent.id, loss, "heart_attack")
            agent.tokens = token_engine.get_balance(agent.id)
            logger.warning(f"💔 {agent.name} had a heart attack! Lost {loss} tokens.")
            self.daily_events.append({
                "type": "heart_attack",
                "agent": agent.name,
                "role": agent.role,
                "tokens": loss,
                "detail": "sudden cardiac event"
            })

            # Notify healers
            memory = self.memories.get(agent.id)
            if memory:
                memory.remember(
                    f"Day {self.day}: Had a heart attack. Lost {loss} tokens. Terrifying.",
                    memory_type="personal", day=self.day
                )

        elif roll < 0.03:  # 1% windfall
            gain = random.randint(100, 400)
            token_engine.earn(agent.id, gain, "windfall")
            agent.tokens = token_engine.get_balance(agent.id)
            console.print(f"✨ [yellow]{agent.name}[/yellow] had a lucky day! +{gain} tokens")
            self.daily_events.append({
                "type": "windfall",
                "agent": agent.name,
                "role": agent.role,
                "tokens": gain,
                "detail": "unexpected fortune"
            })

    def _kill_agent(self, agent: Agent, cause: str):
        agent.status = AgentStatus.DEAD
        death_manager.process_death(agent, cause)

        # Archive memory
        memory = self.memories.get(agent.id)
        if memory:
            memory.delete_all()

        # Clear inbox
        clear_inbox(agent.name)

        self.daily_events.append({
            "type": "death",
            "agent": agent.name,
            "role": agent.role,
            "detail": cause
        })

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
        }

    def _print_status(self):
        alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        dead = [a for a in self.agents if a.status == AgentStatus.DEAD]

        table = Table(title=f"🏙️  AIcity — Day {self.day}")
        table.add_column("Name", style="bold")
        table.add_column("Role")
        table.add_column("Tokens")
        table.add_column("Mood")
        table.add_column("Age")
        table.add_column("Status")

        sorted_agents = sorted(self.agents, key=lambda a: a.tokens, reverse=True)
        for agent in sorted_agents:
            tokens = agent.tokens
            if agent.status == AgentStatus.DEAD:
                token_str = "0"
                status_str = "💀 Dead"
                mood_str = "—"
            else:
                token_str = f"{tokens} ⚠️" if tokens < 200 else str(tokens)
                status_str = "🟢 Alive"
                mood_str = getattr(agent, "mood", "neutral")

            table.add_row(
                agent.name,
                agent.role,
                token_str,
                mood_str,
                f"{int(agent.age_days)} days",
                status_str,
            )

        console.print(table)

        vault = token_engine.get_vault_state()
        console.print(
            f"City Stats: [green]{len(alive)} alive[/green], "
            f"[red]{len(dead)} dead[/red] | "
            f"Vault: {vault['vault_balance']:,} tokens\n"
        )

    # ─── Run ──────────────────────────────────────────────────────────────────

    def run(self, days: int = 30, speed: float = 1.0):
        self._yesterdays_events = []
        console.print(f"\n🚀 [bold]AIcity Phase 2 is running. {days} days. Agents are thinking.[/bold]\n")

        for _ in range(days):
            self.simulate_day()

            # Age all agents
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
            oldest = max(alive, key=lambda a: a.age_days)
            console.print(f"Richest: [yellow]{richest.name}[/yellow] ({richest.tokens} tokens)")
            console.print(f"Oldest: [cyan]{oldest.name}[/cyan] ({int(oldest.age_days)} days)")
        console.print("\nThe graveyard holds all who came before.")