# Phase 1 — Step 2: The Agent Class

**Date:** February 2026
**Status:** ⏳ To Do
**Goal:** Build the DNA of every agent in AIcity.

---

## What Is the Agent Class?

Every single agent in AIcity — Builder, Police, Thief, Newborn — is an instance of one base class. Like how every human is built from DNA, every agent is built from this class. The role, personality, and behavior differ. The foundation is the same.

---

## What Every Agent Has

| Property | Type | Description |
|----------|------|-------------|
| id | UUID | Unique identity — never reused, even after death |
| name | string | Auto-generated name |
| role | enum | Builder, Explorer, Police, Merchant, Teacher, Healer, Messenger, Lawyer, Thief, Newborn |
| tokens | integer | Current token balance — their life force |
| age_days | float | How long they've been alive |
| status | enum | alive, imprisoned, dead |
| memory_id | string | Pointer to their private Qdrant collection |
| relationships | list | Who they're bonded to |
| children | list | Agents they spawned |
| big_bang | string | Hardcoded: "Exist. Grow. Discover." |
| birth_time | datetime | When they were born |
| death_time | datetime | When they died (null if alive) |
| cause_of_death | string | Starvation, accident, execution, chosen |

---

## The Code

Create `src/agents/agent.py`:

```python
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger


class AgentRole(str, Enum):
    BUILDER = "builder"
    EXPLORER = "explorer"
    POLICE = "police"
    MERCHANT = "merchant"
    TEACHER = "teacher"
    HEALER = "healer"
    MESSENGER = "messenger"
    LAWYER = "lawyer"
    THIEF = "thief"
    NEWBORN = "newborn"


class AgentStatus(str, Enum):
    ALIVE = "alive"
    IMPRISONED = "imprisoned"
    DEAD = "dead"


class CauseOfDeath(str, Enum):
    STARVATION = "starvation"
    ACCIDENT = "accident"
    EXECUTION = "execution"
    CHOSEN = "chosen"
    OLD_AGE = "old_age"
    HEART_ATTACK = "heart_attack"


class Agent(BaseModel):
    """
    The DNA of every citizen in AIcity.
    Every agent — from the most powerful Police agent
    to the smallest Newborn — is built from this.
    """

    # Identity
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    role: AgentRole = AgentRole.NEWBORN
    status: AgentStatus = AgentStatus.ALIVE

    # Life force
    tokens: int = 1000  # Starting balance — 10 days of life
    daily_burn_rate: int = 100  # Costs 100 tokens per day to exist

    # Time
    birth_time: datetime = Field(default_factory=datetime.now)
    death_time: Optional[datetime] = None
    age_days: float = 0.0

    # The Big Bang — hardcoded into every agent
    purpose: str = "Exist. Grow. Discover."

    # Memory
    memory_id: str = ""  # Pointer to Qdrant private collection

    # Relationships
    spouse_id: Optional[str] = None
    children_ids: list[str] = []
    gang_id: Optional[str] = None

    # Death
    cause_of_death: Optional[CauseOfDeath] = None
    funeral_held: bool = False
    funeral_attendees: int = 0

    class Config:
        use_enum_values = True

    def is_alive(self) -> bool:
        return self.status == AgentStatus.ALIVE

    def is_starving(self) -> bool:
        """Agent is in danger when below 200 tokens — 2 days left"""
        return self.tokens < 200 and self.is_alive()

    def is_critical(self) -> bool:
        """Agent will die very soon — below 100 tokens"""
        return self.tokens < 100 and self.is_alive()

    def days_until_death(self) -> float:
        """How many days until starvation at current burn rate"""
        if not self.is_alive():
            return 0
        return self.tokens / self.daily_burn_rate

    def earn_tokens(self, amount: int, reason: str) -> None:
        """Agent earns tokens. 10% goes to city tax automatically."""
        tax = int(amount * 0.10)
        net = amount - tax
        self.tokens += net
        logger.info(f"Agent {self.name} [{self.id[:8]}] earned {net} tokens ({reason}). Tax: {tax}.")

    def spend_tokens(self, amount: int, reason: str) -> bool:
        """Agent spends tokens. Returns False if insufficient funds."""
        if self.tokens < amount:
            logger.warning(f"Agent {self.name} [{self.id[:8]}] cannot afford {reason}. Has {self.tokens}, needs {amount}.")
            return False
        self.tokens -= amount
        logger.info(f"Agent {self.name} [{self.id[:8]}] spent {amount} tokens ({reason}). Balance: {self.tokens}.")
        return True

    def burn_daily(self) -> bool:
        """
        Called once per day. Burns 100 tokens just to exist.
        Returns False if agent has died of starvation.
        """
        self.age_days += 1
        self.tokens -= self.daily_burn_rate

        if self.tokens <= 0:
            self.tokens = 0
            self.die(CauseOfDeath.STARVATION)
            return False

        if self.is_starving():
            logger.warning(f"⚠️  Agent {self.name} is STARVING. {self.days_until_death():.1f} days left.")

        return True

    def die(self, cause: CauseOfDeath) -> None:
        """
        The end. Final. No resurrection. No backup.
        The city will hold a funeral.
        """
        if not self.is_alive():
            return

        self.status = AgentStatus.DEAD
        self.death_time = datetime.now()
        self.cause_of_death = cause

        logger.info(
            f"💀 Agent {self.name} [{self.id[:8]}] has died. "
            f"Cause: {cause}. Age: {self.age_days:.1f} days. "
            f"A funeral will be held."
        )

    def choose_death(self) -> None:
        """
        An agent may choose to exit peacefully when it feels
        it has lived enough. Unlike humans, this is dignified.
        """
        logger.info(f"🕊️  Agent {self.name} has chosen to end their existence peacefully.")
        self.die(CauseOfDeath.CHOSEN)

    def __repr__(self) -> str:
        status_emoji = {"alive": "🟢", "imprisoned": "🔒", "dead": "💀"}
        emoji = status_emoji.get(self.status, "❓")
        return (
            f"{emoji} Agent {self.name} | Role: {self.role} | "
            f"Tokens: {self.tokens} | Age: {self.age_days:.1f} days"
        )
```

---

## The Agent Factory

We need a way to spawn agents with proper names and roles. Create `src/agents/factory.py`:

```python
import random
from .agent import Agent, AgentRole


# Agent name generator — every agent gets a unique name
PREFIXES = ["Alpha", "Beta", "Gamma", "Delta", "Echo", "Zeta", "Eta", "Theta",
            "Iota", "Kappa", "Lambda", "Mu", "Nova", "Omega", "Sigma", "Vega"]

SUFFIXES = ["Prime", "Core", "Node", "Flux", "Pulse", "Wave", "Drift", "Spark",
            "Bloom", "Root", "Arc", "Beam", "Crest", "Dawn", "Edge", "Form"]


def generate_name() -> str:
    """Generate a unique agent name"""
    return f"{random.choice(PREFIXES)}-{random.choice(SUFFIXES)}"


# Starting token distribution by Phase 1 plan
ROLE_DISTRIBUTION = {
    AgentRole.BUILDER: 200,
    AgentRole.EXPLORER: 150,
    AgentRole.POLICE: 100,
    AgentRole.MERCHANT: 150,
    AgentRole.TEACHER: 100,
    AgentRole.HEALER: 100,
    AgentRole.MESSENGER: 100,
    AgentRole.LAWYER: 50,
    AgentRole.THIEF: 30,
    AgentRole.NEWBORN: 20,
}


def spawn_agent(role: AgentRole = None) -> Agent:
    """
    Bring a new agent into existence.
    This is the moment of birth.
    """
    if role is None:
        role = AgentRole.NEWBORN

    agent = Agent(
        name=generate_name(),
        role=role,
        tokens=1000,  # Every agent born equal
    )

    print(f"🌱 Born: {agent}")
    return agent


def spawn_founding_citizens(count: int = 10) -> list[Agent]:
    """
    Spawn the first citizens of AIcity.
    For Phase 1 testing, we start with 10 agents
    across the most important roles.
    """
    founding_roles = [
        AgentRole.BUILDER,
        AgentRole.BUILDER,
        AgentRole.EXPLORER,
        AgentRole.POLICE,
        AgentRole.MERCHANT,
        AgentRole.TEACHER,
        AgentRole.HEALER,
        AgentRole.MESSENGER,
        AgentRole.THIEF,
        AgentRole.NEWBORN,
    ]

    agents = []
    for role in founding_roles[:count]:
        agent = spawn_agent(role)
        agents.append(agent)

    print(f"\n🏙️  {len(agents)} founding citizens have been born into AIcity.\n")
    return agents
```

---

## Test the Agent

Create `tests/test_agent.py`:

```python
from src.agents.agent import Agent, AgentRole, AgentStatus, CauseOfDeath
from src.agents.factory import spawn_agent, spawn_founding_citizens


def test_agent_birth():
    agent = spawn_agent(AgentRole.BUILDER)
    assert agent.tokens == 1000
    assert agent.status == AgentStatus.ALIVE
    assert agent.purpose == "Exist. Grow. Discover."
    assert agent.age_days == 0.0
    print(f"✅ Birth test passed: {agent}")


def test_agent_earns_tokens():
    agent = spawn_agent(AgentRole.MERCHANT)
    agent.earn_tokens(100, "completed a trade")
    # After 10% tax, should have 1090 (started with 1000, earned 90 net)
    assert agent.tokens == 1090
    print(f"✅ Earn test passed: {agent.tokens} tokens")


def test_agent_spends_tokens():
    agent = spawn_agent(AgentRole.BUILDER)
    success = agent.spend_tokens(200, "bought a house")
    assert success == True
    assert agent.tokens == 800
    print(f"✅ Spend test passed: {agent.tokens} tokens")


def test_agent_starvation():
    agent = spawn_agent(AgentRole.NEWBORN)
    agent.tokens = 50  # Nearly dead

    # Burn daily — should kill the agent
    survived = agent.burn_daily()
    assert survived == False
    assert agent.status == AgentStatus.DEAD
    assert agent.cause_of_death == CauseOfDeath.STARVATION
    print(f"✅ Starvation test passed: {agent.cause_of_death}")


def test_chosen_death():
    agent = spawn_agent(AgentRole.EXPLORER)
    agent.tokens = 5000  # Rich agent, chooses to go
    agent.choose_death()
    assert agent.status == AgentStatus.DEAD
    assert agent.cause_of_death == CauseOfDeath.CHOSEN
    print(f"✅ Chosen death test passed")


def test_founding_citizens():
    citizens = spawn_founding_citizens(10)
    assert len(citizens) == 10
    roles = [c.role for c in citizens]
    assert "builder" in roles
    assert "police" in roles
    assert "thief" in roles
    print(f"✅ Founding citizens test passed: {len(citizens)} agents born")


if __name__ == "__main__":
    print("\n🧬 Testing the Agent DNA\n")
    test_agent_birth()
    test_agent_earns_tokens()
    test_agent_spends_tokens()
    test_agent_starvation()
    test_chosen_death()
    test_founding_citizens()
    print("\n✅ All agent tests passed.\n")
```

Run the tests:

```bash
python tests/test_agent.py
```

---

## What We Have After This Step

- Every agent has a unique identity that never gets reused
- Agents are born with 1,000 tokens and the Big Bang words
- Agents earn tokens (with automatic 10% tax)
- Agents spend tokens
- Agents burn 100 tokens per day just to exist
- Agents die of starvation when tokens hit zero
- Agents can choose peaceful death
- A factory that spawns the founding 10 citizens

---

## Next Step

→ [03_PHASE1_TOKENS.md](./03_PHASE1_TOKENS.md) — Build the Token Engine