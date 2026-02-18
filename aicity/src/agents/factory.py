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