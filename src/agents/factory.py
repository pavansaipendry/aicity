import random
from .agent import Agent, AgentRole, AgentStatus


# Agent name generator — every agent gets a unique name
FIRST_NAMES = [
    "Marcus", "Elena", "Kai", "Nadia", "Theo", "Asha", "Luca", "Zara",
    "Omar", "Iris", "Felix", "Mira", "Dario", "Sable", "Renn", "Lyra",
    "Caden", "Vela", "Jasper", "Noor", "Soren", "Ayla", "Ezra", "Tessa",
    "River", "Cleo", "Atlas", "Sage", "Orion", "Luna", "Dante", "Milo",
    "Indra", "Zephyr", "Pax", "Ember", "Juno", "Cyrus", "Nova", "Finn",
]

# Role-flavored last names — adds personality without being too on-the-nose
LAST_NAMES = [
    "Cross", "Vale", "Stone", "Wren", "Drake", "Holt", "Lane", "Marsh",
    "Crane", "Fox", "Reed", "Bloom", "Ward", "Black", "Shaw", "Voss",
    "Hart", "Quinn", "Ash", "Cole", "Grey", "West", "Fenn", "Oakes",
    "Bright", "Storm", "Lowe", "Steele", "Rivers", "Knight",
]


def generate_name(existing_names: set = None) -> str:
    """
    Generate a unique human name for a new AIcity citizen.
    Falls back to numbered variants if all combinations are exhausted (unlikely).
    """
    import random
    existing_names = existing_names or set()

    # Try first + last
    attempts = 0
    while attempts < 200:
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in existing_names:
            return name
        attempts += 1

    # Fallback — add a number suffix
    base = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    i = 2
    while f"{base} {i}" in existing_names:
        i += 1
    return f"{base} {i}"



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
        AgentRole.EXPLORER,
        AgentRole.POLICE,
        AgentRole.MERCHANT,
        AgentRole.TEACHER,
        AgentRole.HEALER,
        AgentRole.MESSENGER,
        AgentRole.THIEF,
        AgentRole.BLACKMAILER,   # Phase 4 — secrets dealer in the founding city
        AgentRole.GANG_LEADER,   # Phase 4 — organizer of the desperate
    ]

    agents = []
    for role in founding_roles[:count]:
        agent = spawn_agent(role)

        # Phase 4: assign bribe_susceptibility to police agents at birth
        # Hidden — never shown in dashboard, never logged publicly
        if agent.role == AgentRole.POLICE or agent.role == "police":
            agent.bribe_susceptibility = random.uniform(0.0, 0.85)

        agents.append(agent)

    print(f"\n🏙️  {len(agents)} founding citizens have been born into AIcity.\n")
    return agents