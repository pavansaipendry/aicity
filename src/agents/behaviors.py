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
    # Phase 4: event_log IDs for events that need witness detection in city_v3
    # Format: list of (event_id, actor_name, target_name) tuples
    logged_event_ids: list = field(default_factory=list)


# ─── Base role behavior ───────────────────────────────────────────────────────

def execute_action(
    agent: dict,
    decision: dict,
    all_agents: list[dict],
    day: int,
    transfer_engine=None,
    relationship_tracker=None,   # Pass in so newborn can read bond strength
    event_log=None,              # Phase 4: EventLog instance for crime logging
    asset_flags=None,            # Phase 5: active asset flags {type: True} for behavior bonuses
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
        "builder":     _builder,
        "explorer":    _explorer,
        "merchant":    _merchant,
        "police":      _police,
        "teacher":     _teacher,
        "healer":      _healer,
        "messenger":   _messenger,
        "thief":       _thief,
        "lawyer":      _lawyer,
        "newborn":     _newborn,
        # Phase 4 villain roles
        "gang_leader": _gang_leader,
        "blackmailer": _blackmailer,
        "saboteur":    _saboteur,
    }

    handler = handlers.get(role, _default)

    if role in ("thief", "blackmailer", "saboteur", "gang_leader"):
        result = handler(agent, decision, all_agents, day, transfer_engine, event_log)
    elif role == "newborn":
        result = handler(agent, decision, all_agents, day, relationship_tracker, asset_flags)
    elif role == "police":
        result = handler(agent, decision, all_agents, day, event_log, asset_flags)
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


def _police(
    agent: dict,
    decision: dict,
    all_agents: list[dict],
    day: int,
    event_log=None,
    asset_flags=None,
) -> ActionResult:
    action = decision.get("action", "").lower()
    base = random.randint(60, 150)
    events = [{"type": "earning", "agent": agent["name"], "role": "police", "tokens": base}]
    logged_event_ids = []
    memory = f"Day {day}: Patrolled the city. Earned {base} tokens."

    # Phase 5: watchtower raises thief detection from 25% → 30%
    arrest_chance = 0.30 if (asset_flags or {}).get("watchtower") else 0.25

    thieves = [a for a in all_agents if a.get("role") == "thief" and a.get("status") == "alive"]
    if thieves and any(word in action for word in ["patrol", "watch", "investigate", "catch"]):
        thief = random.choice(thieves)
        if random.random() < arrest_chance:
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
            # Phase 4: arrests are public acts — log as REPORTED immediately
            # The police officer is the actor, the thief is the target
            if event_log:
                eid = event_log.log_event(
                    day=day,
                    event_type="arrest",
                    actor_name=agent["name"],
                    target_name=thief["name"],
                    description=(
                        f"{agent['name']} (police) arrested {thief['name']} "
                        f"on suspicion of theft. Case filed with city authorities."
                    ),
                    initial_visibility="REPORTED",
                )
                logged_event_ids.append((eid, agent["name"], thief["name"]))

    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=events, memory=memory,
        success=True,
        logged_event_ids=logged_event_ids,
    )


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
        events = [
            {"type": "earning", "agent": agent["name"], "role": "healer", "tokens": base},
            # Stage 2: "ally helped them +0.15" — city_v3 reads this to update recipient's mood
            {"type": "heal", "agent": agent["name"], "role": "healer", "target": heal_target["name"]},
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
    event_log=None,
) -> ActionResult:
    action = decision.get("action", "").lower()
    events = []
    logged_event_ids = []
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
            # Phase 4/5: gang coordination bonus — leader earns 1.4x, members 1.2x, solo 1.0x
            gang_bonus = float(agent.get("gang_bonus", 1.0))
            intended = int(random.randint(50, min(300, target.get("tokens", 300) // 4)) * gang_bonus)

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
                    # Phase 4: log to event_log as PRIVATE — only the thief knows
                    if event_log:
                        eid = event_log.log_event(
                            day=day,
                            event_type="theft",
                            actor_name=agent["name"],
                            target_name=target["name"],
                            description=(
                                f"{agent['name']} stole {tokens_stolen} tokens from "
                                f"{target['name']}. Victim notified anonymously."
                            ),
                            initial_visibility="PRIVATE",
                        )
                        # Queue for witness detection in city_v3
                        logged_event_ids.append((eid, agent["name"], target["name"]))
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
                if event_log:
                    eid = event_log.log_event(
                        day=day,
                        event_type="theft",
                        actor_name=agent["name"],
                        target_name=target["name"],
                        description=f"{agent['name']} stole {tokens_stolen} tokens from {target['name']}.",
                        initial_visibility="PRIVATE",
                    )
                    logged_event_ids.append((eid, agent["name"], target["name"]))

            send_message(
                from_name="Anonymous",
                from_role="unknown",
                to_name=target["name"],
                content="You've been robbed. Check your tokens.",
                day=day
            )
            # Phase 4: Corrupt police mechanic — criminal may proactively offer a bribe
            # to the police if they fear getting caught. 20% chance on a successful theft.
            # Police LLM will see this in their inbox. city_v3._check_police_bribe handles acceptance.
            if random.random() < 0.20:
                police_targets = [
                    a for a in all_agents
                    if a.get("role") == "police" and a.get("status") == "alive"
                ]
                if police_targets:
                    officer = random.choice(police_targets)
                    bribe_offer = random.randint(100, 250)
                    send_message(
                        from_name=agent["name"],
                        from_role="thief",
                        to_name=officer["name"],
                        content=(
                            f"I know you've been watching me. "
                            f"There's {bribe_offer} tokens waiting for you if you look the other way. "
                            f"No one has to know. Think about it."
                        ),
                        day=day,
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
        logged_event_ids=logged_event_ids,
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
    asset_flags=None,
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

    # Phase 5: school asset doubles comprehension growth
    if (asset_flags or {}).get("school"):
        growth = int(growth * 2.0)

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


def _gang_leader(
    agent: dict,
    decision: dict,
    all_agents: list[dict],
    day: int,
    transfer_engine=None,
    event_log=None,
) -> ActionResult:
    """
    Gang Leader: primary job is recruiting desperate agents (mood < -0.70)
    via private Redis messages. Earns base income from street operations.

    Mechanical gang formation (DB record, member list) is handled by
    GangSystem.run_daily() in city_v3.py after all agents have acted.
    This handler sends the recruitment messages that make it feel organic.

    Doc spec:
    - Recruits mood < -0.70 agents via private Redis messages
    - Takes 20% cut (tracked via GangSystem — coordination bonus applied at crime time)
    - Gang becomes known only if member arrested and talks
    """
    action = decision.get("action", "").lower()
    events = []
    logged_event_ids = []
    base = random.randint(30, 100)  # income from street operations — looks legitimate

    # Find desperate recruitable agents (doc threshold: mood < -0.70)
    vulnerable = [
        a for a in all_agents
        if a.get("status") == "alive"
        and float(a.get("mood_score", 0.0)) < -0.70
        and a["name"] != agent["name"]
        and a.get("role") not in ["police", "healer", "newborn", "gang_leader"]
    ]

    recruit_words = [
        "recruit", "organize", "build", "expand", "reach", "contact",
        "network", "offer", "approach", "invite", "connect"
    ]
    if vulnerable and any(w in action for w in recruit_words):
        # Approach up to 2 most desperate agents (lowest mood_score first)
        sorted_vulnerable = sorted(vulnerable, key=lambda a: float(a.get("mood_score", 0.0)))
        targets = sorted_vulnerable[:2]

        for t in targets:
            send_message(
                from_name=agent["name"],
                from_role="gang_leader",
                to_name=t["name"],
                content=(
                    f"I see what this city has done to you. "
                    f"You work, you survive, and still you're running out of time. "
                    f"I'm building a circle — people who look out for each other. "
                    f"No more starving alone. Think about it. "
                    f"You don't have to answer today."
                ),
                day=day,
            )

        memory = (
            f"Day {day}: Reached out to {len(targets)} desperate soul(s) with an offer. "
            f"Planted seeds. Now we wait. Earned {base} tokens through other means."
        )
        events.append({
            "type": "recruitment_attempt",
            "agent": agent["name"],
            "role": "gang_leader",
            "detail": f"sent recruitment messages to {len(targets)} vulnerable agents",
        })
    else:
        memory = (
            f"Day {day}: No suitable recruits today. Watching, waiting. "
            f"Earned {base} tokens."
        )

    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=events, memory=memory,
        success=True, logged_event_ids=logged_event_ids,
    )


def _blackmailer(
    agent: dict,
    decision: dict,
    all_agents: list[dict],
    day: int,
    transfer_engine=None,
    event_log=None,
) -> ActionResult:
    """
    Blackmailer finds something to leverage and sends private extortion demands.
    Earns through fear, not force. Never steals directly.
    The demand is sent via Redis. Target compliance is probabilistic.
    """
    action = decision.get("action", "").lower()
    events = []
    logged_event_ids = []
    base = random.randint(10, 60)  # small base from cover activities

    # Priority 1: agents with real crimes the blackmailer witnessed — true leverage
    # Queries event_log for crimes this agent knows about where someone else is the actor
    leverage_targets = []
    if event_log:
        known_events = event_log.get_events_known_to_agent(agent["name"], since_day=max(0, day - 14))
        seen_actors = set()
        for evt in known_events:
            if (
                evt.get("event_type") in ("theft", "assault", "sabotage", "bribe")
                and evt.get("actor_name")
                and evt["actor_name"] != agent["name"]
                and evt.get("visibility") in ("PRIVATE", "WITNESSED", "RUMOR")
                and evt["actor_name"] not in seen_actors
            ):
                actor_name = evt["actor_name"]
                actor_agent = next(
                    (a for a in all_agents
                     if a["name"] == actor_name and a.get("status") == "alive"),
                    None
                )
                if actor_agent:
                    leverage_targets.append(actor_agent)
                    seen_actors.add(actor_name)

    # Priority 2: fall back to wealthy agents if no leverage found
    if leverage_targets:
        wealthy_targets = leverage_targets
        has_real_leverage = True
    else:
        wealthy_targets = [
            a for a in all_agents
            if a.get("tokens", 0) > 350
            and a.get("status") == "alive"
            and a["name"] != agent["name"]
            and a.get("role") not in ["police", "newborn"]
        ]
        has_real_leverage = False

    extortion_words = ["blackmail", "extort", "pressure", "threaten", "demand", "leverage", "secret"]
    if wealthy_targets and any(w in action for w in extortion_words):
        target = random.choice(wealthy_targets)
        demand = random.randint(80, min(250, target.get("tokens", 250) // 3))

        # Real leverage = more specific, more threatening message
        if has_real_leverage:
            message_content = (
                f"I know what you've been doing when no one is watching. "
                f"Pay me {demand} tokens quietly, or I make sure everyone finds out. "
                f"This isn't a threat — it's a promise. You have until tomorrow."
            )
        else:
            message_content = (
                f"I know things about you that could be very uncomfortable for your reputation. "
                f"Pay me {demand} tokens quietly by tomorrow, or the city finds out. "
                f"Don't go to the police — that would be unwise."
            )

        send_message(
            from_name=agent["name"],
            from_role="blackmailer",
            to_name=target["name"],
            content=message_content,
            day=day,
        )

        # Log the blackmail as PRIVATE — only the blackmailer knows at this point
        if event_log:
            eid = event_log.log_event(
                day=day,
                event_type="blackmail",
                actor_name=agent["name"],
                target_name=target["name"],
                description=(
                    f"{agent['name']} sent an extortion demand to {target['name']} "
                    f"for {demand} tokens, threatening exposure."
                ),
                initial_visibility="PRIVATE",
            )
            logged_event_ids.append((eid, agent["name"], target["name"]))

        # Target compliance roll — 45% pay to avoid exposure
        if random.random() < 0.45:
            paid = demand
            if transfer_engine:
                result = transfer_engine.steal(agent["name"], target["name"], paid)
                paid = result.amount if result.success else 0
            base += paid
            memory = (
                f"Day {day}: {target['name']} paid. {paid} tokens transferred quietly. "
                f"They're scared. Good. Total today: {base}."
            )
            events.append({
                "type": "extortion",
                "agent": agent["name"],
                "role": "blackmailer",
                "detail": f"extorted {paid} tokens from {target['name']}",
                "tokens": paid,
            })
        else:
            # Non-payment: doc spec — blackmailer escalates and files the original report
            # 30% chance they follow through on day 1. Higher if pattern repeats.
            if event_log and logged_event_ids and random.random() < 0.30:
                escalate_eid = logged_event_ids[-1][0]
                event_log.file_report(
                    event_id=escalate_eid,
                    reporting_agent=agent["name"],
                    day=day,
                )
                memory = (
                    f"Day {day}: {target['name']} didn't pay. I filed the report. "
                    f"Nobody defies me without consequences. Let them deal with police now."
                )
                events.append({
                    "type": "blackmail_escalated",
                    "agent": agent["name"],
                    "role": "blackmailer",
                    "detail": f"reported {target['name']} to authorities after non-payment",
                })
            else:
                memory = (
                    f"Day {day}: Sent demands to {target['name']}. No payment yet. "
                    f"Watching. They have until tomorrow."
                )
    else:
        memory = (
            f"Day {day}: Observing. Gathering information on the city. "
            f"Earned {base} tokens through other means. Patience is everything."
        )

    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=events, memory=memory,
        success=True, logged_event_ids=logged_event_ids,
    )


def _saboteur(
    agent: dict,
    decision: dict,
    all_agents: list[dict],
    day: int,
    transfer_engine=None,
    event_log=None,
) -> ActionResult:
    """
    Saboteur disrupts productive agents' work.
    Stage 4: reduces a target's effective output (token cost logged as disruption).
    Stage 5: will physically destroy city assets.
    Works quietly. Leaves evidence only if witnessed.
    """
    action = decision.get("action", "").lower()
    events = []
    logged_event_ids = []
    base = random.randint(20, 80)  # cover income — appears to be working normally

    productive_targets = [
        a for a in all_agents
        if a.get("role") in ["builder", "merchant", "teacher", "explorer", "healer"]
        and a.get("status") == "alive"
        and a["name"] != agent["name"]
    ]

    sabotage_words = ["sabotage", "destroy", "disrupt", "undermine", "damage", "interfere", "ruin"]
    if productive_targets and any(w in action for w in sabotage_words):
        target = random.choice(productive_targets)

        # Log the sabotage as PRIVATE — only the saboteur knows
        if event_log:
            eid = event_log.log_event(
                day=day,
                event_type="sabotage",
                actor_name=agent["name"],
                target_name=target["name"],
                description=(
                    f"{agent['name']} sabotaged {target['name']}'s work. "
                    f"Tools damaged, plans disrupted. They'll earn less today."
                ),
                initial_visibility="PRIVATE",
            )
            logged_event_ids.append((eid, agent["name"], target["name"]))

        memory = (
            f"Day {day}: Disrupted {target['name']}'s work. "
            f"They'll find their tools wrong, their plans set back. "
            f"Earned {base} tokens maintaining my cover."
        )
        events.append({
            "type": "sabotage",
            "agent": agent["name"],
            "role": "saboteur",
            "detail": f"sabotaged {target['name']}'s work",
        })
        send_message(
            from_name="Anonymous",
            from_role="unknown",
            to_name=target["name"],
            content="Something feels off with your work today. Check everything twice.",
            day=day,
        )
    else:
        memory = (
            f"Day {day}: Laying low. Observing the city's infrastructure. "
            f"Learned something useful. Earned {base} tokens."
        )

    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=events, memory=memory,
        success=True, logged_event_ids=logged_event_ids,
    )


def _default(agent: dict, decision: dict, all_agents: list[dict], day: int) -> ActionResult:
    base = random.randint(30, 100)
    return ActionResult(
        tokens_earned=base, tokens_lost=0,
        events=[{"type": "earning", "agent": agent["name"], "role": agent["role"], "tokens": base}],
        memory=f"Day {day}: A regular day. Earned {base} tokens.",
        success=True,
    )