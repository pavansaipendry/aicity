# Phase 1 — Step 6: Running 10 Agents

**Date:** February 2026
**Status:** ⏳ To Do
**Goal:** Bring AIcity to life for the first time. 10 agents, born, living, earning, dying.

---

## This Is The Moment

After Steps 1–5 you have all the pieces. This step puts them together for the first time. You will watch 10 agents:

- Be born with 1,000 tokens each
- Earn tokens by doing their jobs
- Burn 100 tokens per day just to exist
- Starve if they can't earn enough
- Die — with a funeral
- Get archived in the graveyard

This is the first heartbeat of AIcity.

---

## The City Runner

Create `src/os/city.py`:

```python
import time
import random
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.live import Live

from src.agents.factory import spawn_founding_citizens
from src.agents.agent import AgentStatus, CauseOfDeath
from src.economy.token_engine import TokenEngine
from src.memory.memory_system import MemorySystem
from src.os.death_manager import DeathManager

console = Console()


class AICity:
    """
    The heartbeat of AIcity.
    This is OASAI — the Operating System for Artificial Intelligence.
    """

    def __init__(self):
        self.token_engine = TokenEngine()
        self.memory = MemorySystem()
        self.death_manager = DeathManager(self.memory, self.token_engine)
        self.agents = []
        self.day = 0
        logger.info("🏙️  AIcity OS initialized. Waiting for the Big Bang.")

    def big_bang(self, agent_count: int = 10):
        """
        The moment of creation.
        Spawn the first citizens and register them.
        """
        console.print("\n[bold yellow]🌟 THE BIG BANG[/bold yellow]\n")
        console.print("[italic]Exist. Grow. Discover.[/italic]\n")

        self.agents = spawn_founding_citizens(agent_count)

        for agent in self.agents:
            # Register in token engine
            self.token_engine.register_agent(agent.id)
            # Create private memory
            memory_id = self.memory.create_agent_memory(agent.id)
            agent.memory_id = memory_id

        console.print(f"\n[green]✅ {len(self.agents)} citizens have been born into AIcity.[/green]\n")

    def simulate_day(self):
        """
        Simulate one full day in AIcity.
        Agents work, earn, spend, and burn tokens.
        """
        self.day += 1
        console.print(f"\n[bold]━━━ Day {self.day} ━━━[/bold]")

        alive_agents = [a for a in self.agents if a.status == AgentStatus.ALIVE]

        for agent in alive_agents:
            # Each agent earns tokens based on their role
            earnings = self._simulate_work(agent)

            if earnings > 0:
                result = self.token_engine.earn(agent.id, earnings, f"{agent.role}_daily_work")
                agent.tokens += result["net_amount"]

            # Simulate random events
            self._simulate_random_event(agent)

            # Daily existence burn
            agent.tokens -= 100
            agent.age_days += 1

            # Check for starvation
            if agent.tokens <= 0:
                agent.tokens = 0
                agent.cause_of_death = CauseOfDeath.STARVATION
                agent.status = AgentStatus.DEAD
                self.death_manager.process_death(agent, "starvation")

    def _simulate_work(self, agent) -> int:
        """
        Simulate an agent doing their daily work.
        Phase 1 — simplified random earnings.
        Later phases — agents will actually think and decide.
        """
        # Base earnings by role — some roles earn more
        base_earnings = {
            "builder": random.randint(50, 180),
            "explorer": random.randint(30, 500),   # High variance — could discover something
            "police": random.randint(60, 150),
            "merchant": random.randint(40, 200),
            "teacher": random.randint(40, 120),
            "healer": random.randint(40, 120),
            "messenger": random.randint(20, 80),
            "lawyer": random.randint(0, 200),       # Feast or famine
            "thief": random.randint(0, 300),        # High risk, high reward
            "newborn": random.randint(0, 50),       # Still figuring it out
        }

        # 20% chance of earning nothing on any given day
        if random.random() < 0.20:
            return 0

        return base_earnings.get(agent.role, 50)

    def _simulate_random_event(self, agent):
        """
        Random city events that affect agents.
        Phase 1 — simplified. Later phases will be much richer.
        """
        roll = random.random()

        # 2% chance of heart attack (sudden large token drain)
        if roll < 0.02:
            drain = random.randint(200, 500)
            agent.tokens = max(0, agent.tokens - drain)
            logger.warning(f"💔 {agent.name} had a heart attack! Lost {drain} tokens.")

        # 1% chance of windfall (lucky discovery)
        elif roll < 0.03:
            windfall = random.randint(200, 500)
            agent.tokens += windfall
            console.print(f"[green]✨ {agent.name} had a lucky day! +{windfall} tokens[/green]")

    def print_city_status(self):
        """Print a live dashboard of the city"""
        table = Table(title=f"🏙️  AIcity — Day {self.day}", show_lines=True)

        table.add_column("Name", style="cyan")
        table.add_column("Role", style="yellow")
        table.add_column("Tokens", style="green")
        table.add_column("Age", style="blue")
        table.add_column("Status", style="red")

        for agent in sorted(self.agents, key=lambda a: a.tokens, reverse=True):
            status_display = {
                "alive": "🟢 Alive",
                "imprisoned": "🔒 Imprisoned",
                "dead": "💀 Dead",
            }.get(agent.status, "❓")

            token_display = str(agent.tokens)
            if agent.tokens < 200 and agent.status == "alive":
                token_display = f"[red]{agent.tokens} ⚠️[/red]"

            table.add_row(
                agent.name,
                agent.role,
                token_display,
                f"{agent.age_days:.0f} days",
                status_display,
            )

        console.print(table)

        # Vault status
        vault = self.token_engine.get_vault_state()
        alive = len([a for a in self.agents if a.status == "alive"])
        dead = len([a for a in self.agents if a.status == "dead"])

        console.print(f"\n[bold]City Stats:[/bold] "
                     f"Population: [green]{alive}[/green] alive, "
                     f"[red]{dead}[/red] dead | "
                     f"Vault: [yellow]{vault['vault_balance']:,}[/yellow] tokens\n")

    def run(self, days: int = 30, speed: float = 0.5):
        """
        Run AIcity for a number of simulated days.
        speed: seconds between each day (0.5 = fast, 2.0 = slow)
        """
        console.print(f"\n[bold green]🚀 AIcity is now running. Simulating {days} days.[/bold green]\n")

        for _ in range(days):
            self.simulate_day()
            self.print_city_status()
            time.sleep(speed)

            # Stop if everyone is dead
            alive = [a for a in self.agents if a.status == "alive"]
            if not alive:
                console.print("\n[bold red]💀 All agents have died. AIcity has fallen.[/bold red]")
                console.print("[italic]The city will be rebuilt. The graveyard remembers.[/italic]\n")
                break

        console.print("\n[bold yellow]📜 Simulation complete.[/bold yellow]")
        self._print_final_report()

    def _print_final_report(self):
        """Print what happened over the simulation"""
        alive = [a for a in self.agents if a.status == "alive"]
        dead = [a for a in self.agents if a.status == "dead"]

        console.print(f"\n[bold]━━━ FINAL REPORT — Day {self.day} ━━━[/bold]")
        console.print(f"Survivors: [green]{len(alive)}[/green]")
        console.print(f"Deaths: [red]{len(dead)}[/red]")

        if alive:
            richest = max(alive, key=lambda a: a.tokens)
            oldest = max(alive, key=lambda a: a.age_days)
            console.print(f"Richest survivor: [cyan]{richest.name}[/cyan] ({richest.tokens} tokens)")
            console.print(f"Oldest survivor: [cyan]{oldest.name}[/cyan] ({oldest.age_days:.0f} days)")

        console.print("\n[italic]The graveyard holds all who came before.[/italic]\n")
```

---

## The Main Entry Point

Create `main.py` in the root:

```python
from src.os.city import AICity

if __name__ == "__main__":
    # Create the city
    city = AICity()

    # The Big Bang — first 10 agents are born
    city.big_bang(agent_count=10)

    # Run for 30 simulated days
    # speed=0.3 means 0.3 seconds per day — fast enough to watch, slow enough to read
    city.run(days=30, speed=0.3)
```

Run it:

```bash
python main.py
```

---

## What You Will See

A live table updating every 0.3 seconds showing:
- Every agent's name, role, tokens, age, and status
- Agents earning tokens from their work
- Tokens slowly draining from daily existence
- Warning indicators when agents are starving
- Funeral announcements when agents die
- Final report showing who survived

**This is the first heartbeat of AIcity.**

---

## Phase 1 Complete ✅

When you can run `python main.py` and watch 10 agents live, survive, and die — Phase 1 is done.

**What we built:**
- ✅ Full project structure
- ✅ The Agent class — DNA of every citizen
- ✅ Token Engine — the economy's heartbeat
- ✅ Memory System — private houses and city library
- ✅ Death Manager — mortality and funerals
- ✅ The City Runner — OASAI OS bringing it all together

**Ready for Phase 2:** Adding the LLM brain — agents that actually think, decide, and talk to each other.

---

## Next Phase

→ Phase 2 — The Citizens: Give agents real intelligence with LLMs.
   Each agent will think, make decisions, and communicate with other agents.