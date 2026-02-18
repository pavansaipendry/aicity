"""
Role Behaviors — How each agent actually earns tokens in Phase 2.

In Phase 1, earning was random(min, max). 
In Phase 2, earning is determined by what the brain DECIDED to do,
combined with role-specific logic and inter-agent interactions.

Each role has:
    - A base earning range
    - A behavior function that takes the brain's decision and returns tokens earned
    - Special actions unique to that role
"""

import random
from dataclasses import dataclass
from loguru import logger
from src.agents.messaging import send_message, get_inbox, format_inbox_for_brain


@dataclass
class ActionResult:
    tokens_earned: int
    tokens_lost: int
    events: list[dict]       # events for the newspaper
    memory: str              # what to remember about today
    success: bool


# ─── Base role behavior ───────────────────────────────────────────────────────

def execute_action(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    """
    Execute an agent's brain decision and return the result.
    Routes to role-specific handler.

    agent = {id, name, role, tokens, age_days, mood}
    decision = brain output {action, reasoning, message_to, message, mood}
    """
    role = agent["role"]
    action = decision.get("action", "works quietly")

    # Send message if brain decided to
    events = []
    if decision.get("message_to") and decision.get("message"):
        recipient = decision["message_to"]
        # Find recipient in alive agents
        recipient_agents = [a for a in all_agents if a["name"] == recipient and a.get("status") == "alive"]
        if recipient_agents:
            send_message(
                from_name=agent["name"],
                from_role=role,
                to_name=recipient,
                content=decision["message"],
                day=day
            )
            events.append({
                "type": "message",
                "agent": agent["name"],
                "role": role,
                "detail": f"messaged {recipient}: \"{decision['message'][:50]}\"",
            })

    # Route to role handler
    handlers = {
        "builder":   _builder,
        "explorer":  _explorer,
        "merchant":  _merchant,
        "police":    _police,
        "teacher":   _teacher,
        "healer":    _healer,
        "messenger": _messenger,
        "thief":     _thief,
        "lawyer":    _lawyer,
        "newborn":   _newborn,
    }

    handler = handlers.get(role, _default)
    result = handler(agent, decision, all_agents, day)
    result.events.extend(events)
    return result


# ─── Role handlers ────────────────────────────────────────────────────────────

def _builder(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()
    base = random.randint(50, 180)

    # Boost if agent decided to work hard
    if any(word in action for word in ["extra", "hard", "desperate", "night", "overtime"]):
        base = int(base * 1.4)
        memory = f"Day {day}: Pushed hard today — earned {base} tokens through sheer effort."
    elif any(word in action for word in ["invest", "big", "project", "structure"]):
        base = int(base * 1.2)
        memory = f"Day {day}: Took on a larger project. Earned {base} tokens."
    else:
        memory = f"Day {day}: Steady work. Earned {base} tokens."

    return ActionResult(
        tokens_earned=base,
        tokens_lost=0,
        events=[{"type": "earning", "agent": agent["name"], "role": "builder", "tokens": base}],
        memory=memory,
        success=True,
    )


def _explorer(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()

    # Explorers: high variance. Sometimes nothing, sometimes massive.
    roll = random.random()
    if roll < 0.15:  # 15% chance of big discovery
        base = random.randint(300, 600)
        memory = f"Day {day}: Found something extraordinary. Earned {base} tokens. The city will remember this."
        events = [
            {"type": "windfall", "agent": agent["name"], "role": "explorer",
             "tokens": base, "detail": "major discovery"}
        ]
    elif roll < 0.30:  # 15% chance of nothing
        base = random.randint(0, 30)
        memory = f"Day {day}: Came back empty-handed almost. Only {base} tokens today."
        events = [{"type": "earning", "agent": agent["name"], "role": "explorer", "tokens": base}]
    else:
        base = random.randint(60, 200)
        memory = f"Day {day}: A decent expedition. Earned {base} tokens."
        events = [{"type": "earning", "agent": agent["name"], "role": "explorer", "tokens": base}]

    # Boost if brain said to take risks
    if any(word in action for word in ["risk", "deep", "unknown", "dangerous"]):
        base = int(base * 1.3)

    return ActionResult(tokens_earned=base, tokens_lost=0, events=events, memory=memory, success=True)


def _merchant(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()

    # Merchants earn more if they have rich neighbors to trade with
    rich_agents = [a for a in all_agents if a.get("tokens", 0) > 500 and a["name"] != agent["name"]]
    trade_bonus = min(len(rich_agents) * 15, 100)

    base = random.randint(40, 160) + trade_bonus

    if any(word in action for word in ["negotiate", "deal", "trade", "arbitrage"]):
        base = int(base * 1.3)
        memory = f"Day {day}: Closed a good deal today. Earned {base} tokens. The market rewards patience."
    else:
        memory = f"Day {day}: Standard trading day. Earned {base} tokens."

    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=[{"type": "earning", "agent": agent["name"], "role": "merchant", "tokens": base}],
        memory=memory, success=True,
    )


def _police(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()
    base = random.randint(60, 150)
    events = [{"type": "earning", "agent": agent["name"], "role": "police", "tokens": base}]
    memory = f"Day {day}: Patrolled the city. Earned {base} tokens."

    # Check if there's a thief to catch
    thieves = [a for a in all_agents if a.get("role") == "thief" and a.get("status") == "alive"]
    if thieves and any(word in action for word in ["patrol", "watch", "investigate", "catch"]):
        thief = random.choice(thieves)
        if random.random() < 0.25:  # 25% chance of catching a thief
            arrest_bonus = 200
            base += arrest_bonus
            memory = f"Day {day}: Caught {thief['name']} red-handed. Earned {base} tokens for the arrest."
            events.append({
                "type": "arrest",
                "agent": agent["name"],
                "role": "police",
                "detail": f"arrested {thief['name']}"
            })
            # Notify the thief
            send_message(
                from_name=agent["name"],
                from_role="police",
                to_name=thief["name"],
                content=f"You are under arrest. I have reported you to the city authorities.",
                day=day
            )

    return ActionResult(tokens_earned=base, tokens_lost=0, events=events, memory=memory, success=True)


def _teacher(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()

    # Teachers earn based on who's listening — more students = more tokens
    students = [a for a in all_agents
                if a.get("role") in ["newborn", "builder"] and a["name"] != agent["name"]]
    student_bonus = len(students) * 20

    base = random.randint(40, 120) + student_bonus

    if any(word in action for word in ["teach", "mentor", "lesson", "share", "knowledge"]):
        base = int(base * 1.2)
        memory = f"Day {day}: Shared knowledge with the city today. Earned {base} tokens. Teaching is its own reward."
    else:
        memory = f"Day {day}: Quiet teaching day. Earned {base} tokens."

    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=[{"type": "earning", "agent": agent["name"], "role": "teacher", "tokens": base}],
        memory=memory, success=True,
    )


def _healer(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()
    base = random.randint(40, 120)

    # Healers earn more when others are in danger
    critical_agents = [a for a in all_agents
                       if a.get("tokens", 1000) < 200 and a["name"] != agent["name"]]
    if critical_agents:
        heal_target = critical_agents[0]
        heal_bonus = 80
        base += heal_bonus
        # Healers can transfer a small amount of tokens to keep others alive
        # (mechanical healing — Phase 3 will have real token transfers)
        memory = f"Day {day}: Tended to {heal_target['name']} who was in critical condition. Earned {base} tokens."
        events = [
            {"type": "earning", "agent": agent["name"], "role": "healer", "tokens": base},
        ]
        send_message(
            from_name=agent["name"],
            from_role="healer",
            to_name=heal_target["name"],
            content=f"I saw you were struggling. I've done what I can to help. Stay strong.",
            day=day
        )
    else:
        memory = f"Day {day}: No emergencies today. Routine healing work. Earned {base} tokens."
        events = [{"type": "earning", "agent": agent["name"], "role": "healer", "tokens": base}]

    return ActionResult(tokens_earned=base, tokens_lost=0, events=events, memory=memory, success=True)


def _messenger(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    """
    The Messenger earns tokens by delivering messages and writing the newspaper.
    They know everyone's business.
    """
    base = random.randint(30, 100)

    # Messengers earn a small bonus per active conversation in the city
    alive_count = len([a for a in all_agents if a.get("status") == "alive"])
    network_bonus = alive_count * 5
    base += network_bonus

    memory = f"Day {day}: Delivered messages across the city. Wrote the daily paper. Earned {base} tokens."

    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=[{"type": "earning", "agent": agent["name"], "role": "messenger", "tokens": base}],
        memory=memory, success=True,
    )


def _thief(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()
    events = []
    tokens_stolen = 0
    tokens_lost = 0

    # Thieves try to steal from rich agents
    potential_targets = [
        a for a in all_agents
        if a.get("tokens", 0) > 500
        and a.get("status") == "alive"
        and a["name"] != agent["name"]
        and a.get("role") != "newborn"  # Even thieves have a code
    ]

    if potential_targets and any(word in action for word in ["steal", "take", "target", "sneak", "rob"]):
        target = max(potential_targets, key=lambda a: a.get("tokens", 0))  # Target the richest
        steal_attempt = random.random()

        if steal_attempt < 0.45:  # 45% success rate
            tokens_stolen = random.randint(50, min(300, target.get("tokens", 300) // 4))
            memory = f"Day {day}: Successfully stole {tokens_stolen} tokens from {target['name']}. Quick hands today."
            events.append({
                "type": "theft",
                "agent": agent["name"],
                "role": "thief",
                "detail": f"stole {tokens_stolen} tokens from {target['name']}"
            })
            # Notify victim
            send_message(
                from_name="Anonymous",
                from_role="unknown",
                to_name=target["name"],
                content=f"You've been robbed. Check your tokens.",
                day=day
            )
        else:
            # Failed theft — risk of being noticed
            memory = f"Day {day}: Tried to steal from {target['name']} but the timing was wrong. Kept a low profile."
    else:
        # Lay low day — small legitimate earnings
        tokens_stolen = random.randint(0, 80)
        memory = f"Day {day}: Kept it quiet today. Picked up {tokens_stolen} tokens through small scores."

    return ActionResult(
        tokens_earned=tokens_stolen,
        tokens_lost=tokens_lost,
        events=events,
        memory=memory,
        success=tokens_stolen > 0,
    )


def _lawyer(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()
    base = 0
    events = []

    # Lawyers earn big when there are trials, nothing otherwise
    # Phase 2: simplified — they earn when there are arrests or disputes
    has_case = random.random() < 0.3  # 30% chance of having a case

    if has_case:
        base = random.randint(100, 300)
        memory = f"Day {day}: Represented a client in proceedings today. Earned {base} tokens. Justice is profitable."
    else:
        base = random.randint(0, 40)
        memory = f"Day {day}: No cases today. Earned {base} tokens on small consultations."

    events = [{"type": "earning", "agent": agent["name"], "role": "lawyer", "tokens": base}]
    return ActionResult(tokens_earned=base, tokens_lost=0, events=events, memory=memory, success=True)


def _newborn(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()
    base = random.randint(0, 50)

    # Newborns who are actively trying to learn earn a bit more
    if any(word in action for word in ["learn", "watch", "ask", "observe", "explore"]):
        base = int(base * 1.5)
        memory = f"Day {day}: Watched how others work today. Starting to understand this city. Earned {base} tokens."
    else:
        memory = f"Day {day}: Still figuring things out. Earned {base} tokens."

    # Newborns automatically message the Teacher if one exists
    teachers = [a for a in all_agents if a.get("role") == "teacher" and a.get("status") == "alive"]
    events = [{"type": "earning", "agent": agent["name"], "role": "newborn", "tokens": base}]

    if teachers and agent.get("tokens", 1000) < 400:
        teacher = teachers[0]
        send_message(
            from_name=agent["name"],
            from_role="newborn",
            to_name=teacher["name"],
            content=f"I'm struggling to survive. My tokens are running low. Can you teach me how to earn more?",
            day=day
        )

    return ActionResult(tokens_earned=base, tokens_lost=0, events=events, memory=memory, success=True)


def _default(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    base = random.randint(30, 100)
    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=[{"type": "earning", "agent": agent["name"], "role": agent["role"], "tokens": base}],
        memory=f"Day {day}: A regular day. Earned {base} tokens.",
        success=True,
    )