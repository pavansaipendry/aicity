import random

ROLE_PRIORITY = {
    # If none alive of this role, spawn probability weight
    'healer': 3,      # critical — city needs healers
    'merchant': 2,    # important for economy  
    'teacher': 2,     # important for newborns
    'builder': 1,
    'explorer': 1,
    'police': 1,
    'messenger': 1,
    'thief': 0.5,     # spawn less often
    'newborn': 0,     # never spawn a newborn directly
}

POPULATION_FLOOR = 6

def check_births(city) -> list:
    """Called each day. Returns list of newly born agents."""
    alive = [a for a in city.agents if a.alive]
    born = []
    
    while len(alive) < POPULATION_FLOOR:
        role = pick_needed_role(alive)
        existing_names = {a.name for a in city.agents}  # ← ADD THIS
        name = generate_name(existing_names)             # ← CHANGE THIS
        new_agent = Agent(name=name, role=role, tokens=1000)
        city.agents.append(new_agent)
        alive.append(new_agent)
        born.append(new_agent)
        
        logger.info(f"🌱 New citizen born: {name} ({role})")
    
    return born

def pick_needed_role(alive_agents: list) -> str:
    """Pick the role the city most needs."""
    alive_roles = {a.role for a in alive_agents}
    
    # First: fill completely missing critical roles
    for role in ['healer', 'merchant', 'police']:
        if role not in alive_roles:
            return role
    
    # Then: weighted random from all roles
    import random
    roles = list(ROLE_PRIORITY.keys())
    weights = [ROLE_PRIORITY[r] for r in roles]
    return random.choices(roles, weights=weights)[0]

def generate_name(existing_names: set = None) -> str:
    existing_names = existing_names or set()

    FIRST_NAMES = [
        "Marcus", "Elena", "Kai", "Nadia", "Theo", "Asha", "Luca", "Zara",
        "Omar", "Iris", "Felix", "Mira", "Dario", "Sable", "Renn", "Lyra",
        "Caden", "Vela", "Jasper", "Noor", "Soren", "Ayla", "Ezra", "Tessa",
        "River", "Cleo", "Atlas", "Sage", "Orion", "Luna", "Dante", "Milo",
        "Indra", "Zephyr", "Pax", "Ember", "Juno", "Cyrus", "Nova", "Finn",
    ]
    LAST_NAMES = [
        "Cross", "Vale", "Stone", "Wren", "Drake", "Holt", "Lane", "Marsh",
        "Crane", "Fox", "Reed", "Bloom", "Ward", "Black", "Shaw", "Voss",
        "Hart", "Quinn", "Ash", "Cole", "Grey", "West", "Fenn", "Oakes",
        "Bright", "Storm", "Lowe", "Steele", "Rivers", "Knight",
    ]

    attempts = 0
    while attempts < 200:
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in existing_names:
            return name
        attempts += 1

    base = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    i = 2
    while f"{base} {i}" in existing_names:
        i += 1
    return f"{base} {i}"