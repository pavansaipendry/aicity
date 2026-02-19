"""
Role Behaviors — How each agent actually earns tokens in Phase 2.

In Phase 1, earning was random(min, max). 
In Phase 2, earning is determined by what the brain DECIDED to do,
combined with role-specific logic and inter-agent interactions.

Each role has:
    - A base earning range
    - A behavior function that takes the brain's decision and returns tokens earned
    - Special actions unique to that role

Phase 3 change: pass `transfer_engine` into execute_action() and theft
becomes a real bilateral transfer. Everything else is unchanged.

Phase 4 change: newborn comprehension system. The newborn builds a
comprehension score each day based on teacher presence and bond strength.
At 100, graduation fires and the brain chooses a role freely.
"""

import random
from dataclasses import dataclass, field
from loguru import logger
from src.agents.messaging import send_message, get_inbox, format_inbox_for_brain


@dataclass
class ActionResult:
    tokens_earned: int
    tokens_lost: int
    events: list[dict]
    memory: str
    success: bool
    # Graduation payload — only set when a newborn is ready to choose their role
    graduation_ready: bool = False
    graduation_statement: str = ""


# ─── Base role behavior ───────────────────────────────────────────────────────

def execute_action(
    agent: dict,
    decision: dict,
    all_agents: list[dict],
    day: int,
    transfer_engine=None,
    relationship_tracker=None,   # Pass in so newborn can read bond strength
) -> ActionResult:
    """
    Execute an agent's brain decision and return the result.
    Routes to role-specific handler.
    """
    role = agent["role"]
    action = decision.get("action", "works quietly")

    events = []
    if decision.get("message_to") and decision.get("message"):
        recipient = decision["message_to"]
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

    if role == "thief":
        result = handler(agent, decision, all_agents, day, transfer_engine)
    elif role == "newborn":
        result = handler(agent, decision, all_agents, day, relationship_tracker)
    else:
        result = handler(agent, decision, all_agents, day)

    result.events.extend(events)
    return result


# ─── Role handlers ────────────────────────────────────────────────────────────

def _builder(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()
    base = random.randint(50, 180)

    if any(word in action for word in ["extra", "hard", "desperate", "night", "overtime"]):
        base = int(base * 1.4)
        memory = f"Day {day}: Pushed hard today — earned {base} tokens through sheer effort."
    elif any(word in action for word in ["invest", "big", "project", "structure"]):
        base = int(base * 1.2)
        memory = f"Day {day}: Took on a larger project. Earned {base} tokens."
    else:
        memory = f"Day {day}: Steady work. Earned {base} tokens."

    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=[{"type": "earning", "agent": agent["name"], "role": "builder", "tokens": base}],
        memory=memory, success=True,
    )


def _explorer(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()
    roll = random.random()

    if roll < 0.15:
        base = random.randint(300, 600)
        memory = f"Day {day}: Found something extraordinary. Earned {base} tokens. The city will remember this."
        events = [{"type": "windfall", "agent": agent["name"], "role": "explorer",
                   "tokens": base, "detail": "major discovery"}]
    elif roll < 0.30:
        base = random.randint(0, 30)
        memory = f"Day {day}: Came back empty-handed almost. Only {base} tokens today."
        events = [{"type": "earning", "agent": agent["name"], "role": "explorer", "tokens": base}]
    else:
        base = random.randint(60, 200)
        memory = f"Day {day}: A decent expedition. Earned {base} tokens."
        events = [{"type": "earning", "agent": agent["name"], "role": "explorer", "tokens": base}]

    if any(word in action for word in ["risk", "deep", "unknown", "dangerous"]):
        base = int(base * 1.3)

    return ActionResult(tokens_earned=base, tokens_lost=0, events=events, memory=memory, success=True)


def _merchant(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    action = decision.get("action", "").lower()
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

    thieves = [a for a in all_agents if a.get("role") == "thief" and a.get("status") == "alive"]
    if thieves and any(word in action for word in ["patrol", "watch", "investigate", "catch"]):
        thief = random.choice(thieves)
        if random.random() < 0.25:
            arrest_bonus = 200
            base += arrest_bonus
            memory = f"Day {day}: Caught {thief['name']} red-handed. Earned {base} tokens for the arrest."
            events.append({
                "type": "arrest",
                "agent": agent["name"],
                "role": "police",
                "detail": f"arrested {thief['name']}"
            })
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

    critical_agents = [a for a in all_agents
                       if a.get("tokens", 1000) < 200 and a["name"] != agent["name"]]
    if critical_agents:
        heal_target = critical_agents[0]
        base += 80
        memory = f"Day {day}: Tended to {heal_target['name']} who was in critical condition. Earned {base} tokens."
        events = [{"type": "earning", "agent": agent["name"], "role": "healer", "tokens": base}]
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
    base = random.randint(30, 100)
    alive_count = len([a for a in all_agents if a.get("status") == "alive"])
    base += alive_count * 5
    memory = f"Day {day}: Delivered messages across the city. Wrote the daily paper. Earned {base} tokens."

    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=[{"type": "earning", "agent": agent["name"], "role": "messenger", "tokens": base}],
        memory=memory, success=True,
    )


def _thief(
    agent: dict,
    decision: dict,
    all_agents: list[dict],
    day: int,
    transfer_engine=None,
) -> ActionResult:
    action = decision.get("action", "").lower()
    events = []
    tokens_stolen = 0

    potential_targets = [
        a for a in all_agents
        if a.get("tokens", 0) > 500
        and a.get("status") == "alive"
        and a["name"] != agent["name"]
        and a.get("role") != "newborn"
    ]

    if potential_targets and any(word in action for word in ["steal", "take", "target", "sneak", "rob"]):
        target = max(potential_targets, key=lambda a: a.get("tokens", 0))

        if random.random() < 0.45:
            intended = random.randint(50, min(300, target.get("tokens", 300) // 4))

            if transfer_engine is not None:
                result = transfer_engine.steal(agent["name"], target["name"], intended)
                tokens_stolen = result.amount

                if result.success:
                    memory = (
                        f"Day {day}: Stole {tokens_stolen} tokens from {target['name']}. "
                        f"They actually lost it — {result.from_balance_after} tokens left in their pocket."
                    )
                    events.append({
                        "type": "theft",
                        "agent": agent["name"],
                        "role": "thief",
                        "detail": f"stole {tokens_stolen} tokens from {target['name']} (real transfer)",
                    })
                else:
                    tokens_stolen = 0
                    memory = f"Day {day}: {target['name']} was too broke to steal from. Kept a low profile."
            else:
                tokens_stolen = intended
                memory = f"Day {day}: Successfully stole {tokens_stolen} tokens from {target['name']}. Quick hands today."
                events.append({
                    "type": "theft",
                    "agent": agent["name"],
                    "role": "thief",
                    "detail": f"stole {tokens_stolen} tokens from {target['name']}",
                })

            send_message(
                from_name="Anonymous",
                from_role="unknown",
                to_name=target["name"],
                content="You've been robbed. Check your tokens.",
                day=day
            )
        else:
            memory = f"Day {day}: Tried to steal from {target['name']} but the timing was wrong. Kept a low profile."
    else:
        tokens_stolen = random.randint(0, 80)
        memory = f"Day {day}: Kept it quiet today. Picked up {tokens_stolen} tokens through small scores."

    return ActionResult(
        tokens_earned=tokens_stolen, tokens_lost=0,
        events=events, memory=memory,
        success=tokens_stolen > 0,
    )


def _lawyer(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    has_case = random.random() < 0.3

    if has_case:
        base = random.randint(100, 300)
        memory = f"Day {day}: Represented a client in proceedings today. Earned {base} tokens. Justice is profitable."
    else:
        base = random.randint(0, 40)
        memory = f"Day {day}: No cases today. Earned {base} tokens on small consultations."

    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=[{"type": "earning", "agent": agent["name"], "role": "lawyer", "tokens": base}],
        memory=memory, success=True,
    )


# ─── Newborn system ───────────────────────────────────────────────────────────

def _newborn(
    agent: dict,
    decision: dict,
    all_agents: list[dict],
    day: int,
    relationship_tracker=None,
) -> ActionResult:
    """
    The newborn earns very little but grows a comprehension score each day.

    Score growth depends on:
    - Whether a teacher is assigned and alive (+base)
    - The bond strength between newborn and teacher (multiplier)
    - Active learning behavior in today's decision (+bonus)

    At score >= 100: graduation_ready flag fires.
    The city_v3 runner detects this and calls the graduation brain prompt.

    The newborn's memories are the corruption vector.
    Daily newspaper exposure to crime seeds the thief path naturally.
    """
    action = decision.get("action", "").lower()
    events = []

    # ── Small daily earning ────────────────────────────────────────────────
    base_earn = random.randint(0, 50)
    is_actively_learning = any(
        word in action for word in ["learn", "watch", "ask", "observe", "study", "practice", "try"]
    )
    if is_actively_learning:
        base_earn = int(base_earn * 1.5)

    # ── Comprehension score growth ─────────────────────────────────────────
    current_score = agent.get("comprehension_score", 0)

    # Find assigned teacher
    assigned_teacher = agent.get("assigned_teacher")
    teacher_alive = any(
        a["name"] == assigned_teacher and a.get("status") == "alive"
        for a in all_agents
    ) if assigned_teacher else False

    if not teacher_alive:
        # No teacher — look for any alive teacher
        live_teachers = [a for a in all_agents if a.get("role") == "teacher" and a.get("status") == "alive"]
        if live_teachers:
            assigned_teacher = live_teachers[0]["name"]
            teacher_alive = True

    # Bond strength affects learning speed
    bond_strength = 0.0
    if teacher_alive and relationship_tracker:
        bond_strength = relationship_tracker.get_bond(agent["name"], assigned_teacher)
        # bond is -1.0 to 1.0, normalize to 0.0–1.0 for our purposes
        bond_strength = max(0.0, bond_strength)

    # Base growth: 2–5 per day without teacher, 6–12 with teacher
    if teacher_alive:
        # bond_strength 0.0 → +6/day, bond_strength 1.0 → +12/day
        growth = random.randint(6, 12)
        growth = int(growth * (0.7 + 0.3 * bond_strength))
    else:
        # Learning alone from the city — slow
        growth = random.randint(2, 5)

    # Active learning gives a small bonus
    if is_actively_learning:
        growth = int(growth * 1.2)

    new_score = min(100, current_score + growth)

    # ── Build memory ───────────────────────────────────────────────────────
    if new_score >= 100 and current_score < 100:
        # Graduation moment
        memory = (
            f"Day {day}: Something shifted today. I feel like I finally understand this city. "
            f"I know who I want to be. Comprehension complete."
        )
        events.append({
            "type": "graduation_ready",
            "agent": agent["name"],
            "detail": "newborn reached 100% comprehension — ready to choose role",
            "assigned_teacher": assigned_teacher,
        })
        logger.info(f"🎓 {agent['name']} has reached 100% comprehension. Graduation pending.")
    elif teacher_alive:
        memory = (
            f"Day {day}: Learned more from {assigned_teacher} today. "
            f"Understanding the city better. Comprehension: {new_score}%. Earned {base_earn} tokens."
        )
    else:
        memory = (
            f"Day {day}: Figuring things out on my own today. "
            f"Watched how others work. Comprehension: {new_score}%. Earned {base_earn} tokens."
        )

    # ── Outreach ───────────────────────────────────────────────────────────
    # Ask teacher for guidance if assigned
    if teacher_alive and random.random() < 0.4:
        urgency = "running low on tokens — " if agent.get("tokens", 1000) < 400 else ""
        send_message(
            from_name=agent["name"],
            from_role="newborn",
            to_name=assigned_teacher,
            content=f"I'm {urgency}trying to understand my place here. What should I focus on today?",
            day=day
        )
    elif not teacher_alive and agent.get("tokens", 1000) < 400:
        # No teacher — send distress to whoever might help
        healers = [a for a in all_agents if a.get("role") == "healer" and a.get("status") == "alive"]
        if healers:
            send_message(
                from_name=agent["name"],
                from_role="newborn",
                to_name=healers[0]["name"],
                content="I'm struggling. My tokens are low and I don't have a teacher. I don't know what to do.",
                day=day
            )

    events.append({"type": "earning", "agent": agent["name"], "role": "newborn", "tokens": base_earn})

    return ActionResult(
        tokens_earned=base_earn,
        tokens_lost=0,
        events=events,
        memory=memory,
        success=True,
        graduation_ready=(new_score >= 100 and current_score < 100),
        graduation_statement=f"comprehension_score:{new_score}|teacher:{assigned_teacher}",
    )


def _default(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    base = random.randint(30, 100)
    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=[{"type": "earning", "agent": agent["name"], "role": agent["role"], "tokens": base}],
        memory=f"Day {day}: A regular day. Earned {base} tokens.",
        success=True,
    )