import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger
from pydantic import BaseModel, Field, ConfigDict


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

    model_config = ConfigDict(use_enum_values=True)

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