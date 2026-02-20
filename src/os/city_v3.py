"""
AIcity Phase 3 — The City Runner with real transfers, trials, births,
persistent state, relationships, and live dashboard.

New vs Phase 2:
    - Real token transfers (theft moves tokens from victim)
    - Trial system (arrests trigger LLM judge)
    - Births (population floor of 6)
    - Persistent state (PostgreSQL save/load)
    - Relationships (bond tracking)
    - Live dashboard (WebSocket broadcast)

Run: python main_phase3.py
"""

import time
import random
import asyncio
import requests as _requests
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.agents.agent import Agent, AgentRole, AgentStatus
from src.agents.factory import spawn_founding_citizens
from src.agents.brain import AgentBrain
from src.agents.behaviors import execute_action
from src.agents.messaging import get_inbox, format_inbox_for_brain, clear_inbox
from src.agents.newspaper import CityNewspaper
from src.agents.relationships import RelationshipTracker
from src.economy.token_engine import TokenEngine
from src.economy.transfers import TransferEngine
from src.memory.memory_v2 import AgentMemory, CityKnowledge
from src.os.death_manager import DeathManager
from src.justice.court import Court
from src.justice.judge import JudgeAgent
from src.city.event_log import EventLog
from src.justice.case_manager import CaseManager
from src.agents.gang import GangSystem
from src.economy.projects import ProjectSystem, ASSET_SPECS, BUILD_PRIORITY
from src.economy.assets import AssetSystem
from src.city.position_manager import PositionManager
from src.city.home_manager import HomeManager
from src.city.meeting_manager import MeetingManager

# Dashboard import — optional, won't crash if not running
try:
    from src.dashboard.server import update_state, broadcast as _broadcast
    DASHBOARD = True
except ImportError:
    DASHBOARD = False

console = Console()
token_engine = TokenEngine()
death_manager = DeathManager(memory_system=None, token_engine=token_engine)
city_knowledge = CityKnowledge()
newspaper = CityNewspaper()

POPULATION_FLOOR = 6


def _broadcast_sync(event: dict):
    """Fire-and-forget dashboard broadcast from sync code."""
    try:
        r = _requests.post("http://localhost:8000/api/event", json=event, timeout=1)
        print(f"✅ POST {event.get('type')} → {r.status_code}")
    except Exception as e:
        print(f"❌ POST FAILED: {e}")


class AICity:
    def __init__(self):
        self.agents: list[Agent] = []
        self.brains: dict[str, AgentBrain] = {}
        self.memories: dict[str, AgentMemory] = {}
        self.relationships = RelationshipTracker()
        self.transfer_engine: TransferEngine | None = None   # built after big_bang
        self.court: Court | None = None
        self.day = 0
        self.daily_events: list[dict] = []
        self.city_news = "Welcome to AIcity. A new civilization begins."
        self._yesterdays_events: list[dict] = []
        # Phase 4: event log + case manager + gang system
        self.event_log = EventLog()
        self.case_manager = CaseManager(event_log=self.event_log)
        self.gang_system = GangSystem(event_log=self.event_log)
        # Phase 5: city infrastructure — projects + assets
        self.asset_system = AssetSystem(event_log=self.event_log)
        self.project_system = ProjectSystem(event_log=self.event_log)
        # Phase 5: position, home, meeting managers
        self.position_manager = PositionManager()
        self.home_manager = HomeManager()
        self.meeting_manager: MeetingManager | None = None  # set in _init_phase3_systems
        self._agent_last_decisions: dict[str, dict] = {}
        logger.info("AIcity Phase 4/5 initialized.")

    # ─── Big Bang ─────────────────────────────────────────────────────────────

    def big_bang(self, n: int = 10):
        console.print(Panel.fit("🌟 THE BIG BANG\n\nExist. Grow. Discover.", style="bold yellow"))

        agents_data = spawn_founding_citizens(n)
        for agent in agents_data:
            token_engine.register_agent(agent.id)
            self.brains[agent.id] = AgentBrain(agent.id, agent.name, agent.role)
            self.memories[agent.id] = AgentMemory(agent.id, agent.name)
            self.agents.append(agent)
            console.print(f"🌱 Born: [bold green]{agent.name}[/bold green] ({agent.role})")

        self._init_phase3_systems()
        self._seed_constitution()
        # Phase 5: assign starting positions on the map
        self.position_manager.assign_starting_positions(self.agents)
        console.print(f"\n🏙️  [bold]{n} founding citizens have entered AIcity.[/bold]\n")

    def _init_phase3_systems(self):
        """Set up transfer engine, court, event_log memory ref, and Phase 5 managers."""
        agent_dicts = [self._agent_to_dict(a) for a in self.agents]
        self.transfer_engine = TransferEngine(agent_dicts, token_engine=token_engine)
        judge = JudgeAgent()
        self.court = Court(judge_agent=judge, transfer_engine=self.transfer_engine)
        self._refresh_event_log_memories()
        # Phase 5: initialize MeetingManager with its own DB connection
        try:
            import psycopg2
            from dotenv import load_dotenv
            import os as _os
            load_dotenv()
            db_url = _os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:password@localhost:5432/aicity"
            )
            _meeting_conn = psycopg2.connect(db_url)
            self.meeting_manager = MeetingManager(db_conn=_meeting_conn)
            logger.info("Phase 5: MeetingManager initialized with DB connection.")
        except Exception as e:
            logger.warning(f"MeetingManager: DB connection failed — {e}. Meetings won't be persisted.")
            self.meeting_manager = MeetingManager(db_conn=None)

    def _refresh_event_log_memories(self):
        """
        Give EventLog a name-keyed memory dict so it can store witness
        fragments in Qdrant when crimes are detected.
        Called after any new agent is born.
        """
        name_memories = {
            a.name: self.memories[a.id]
            for a in self.agents
            if a.id in self.memories
        }
        self.event_log.set_memories(name_memories)

    # ─── Load from saved state (Phase 3) ─────────────────────────────────────

    def load_from_save(self, saved: dict):
        """Restore city from PostgreSQL save."""
        self.day = saved["day"]
        for a in saved["agents"]:
            agent = Agent(
                name=a["name"],
                role=a["role"],
                tokens=a["tokens"],
            )
            agent.age_days = a.get("age_days", 0)
            agent.status = AgentStatus.ALIVE if a.get("alive", True) else AgentStatus.DEAD
            agent.comprehension_score = a.get("comprehension_score", 0)
            agent.assigned_teacher = a.get("assigned_teacher", None)
            agent.mood_score = a.get("mood_score", 0.0)
            if a.get("cause_of_death"):
                agent.cause_of_death = a["cause_of_death"]
            token_engine.register_agent(agent.id)
            token_engine.earn(agent.id, a["tokens"], "restore")
            self.brains[agent.id] = AgentBrain(agent.id, agent.name, agent.role)
            self.memories[agent.id] = AgentMemory(agent.id, agent.name)
            self.agents.append(agent)

        self._init_phase3_systems()
        # Phase 5: assign starting positions on restore
        self.position_manager.assign_starting_positions(self.agents)
        if saved.get("last_paper"):
            self.city_news = saved["last_paper"].get("body", self.city_news)

        logger.info(f"🔄 Restored {len(self.agents)} agents from Day {self.day}")

    def _seed_constitution(self):
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

    # ─── Daily Simulation ─────────────────────────────────────────────────────

    def simulate_day(self, persistence=None):
        self.day += 1
        self.daily_events = []
        console.rule(f"[bold]━━━ Day {self.day} ━━━[/bold]")

        alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        self._agent_last_decisions.clear()

        # Phase 5: dawn → morning — agents wake and walk to their work zones
        self._update_positions("morning")
        _broadcast_sync({"type": "time_phase", "phase": "morning", "day": self.day})
        _broadcast_sync({"type": "positions", "agents": [
            {"name": a.name, "x": round(a.x, 1), "y": round(a.y, 1),
             "role": a.role, "status": "alive"}
            for a in alive
        ]})

        # 1. Write newspaper — filter to PUBLIC event types only
        # Newspaper cannot see private crimes (theft, blackmail, sabotage, recruitment)
        _NEWSPAPER_PUBLIC_TYPES = {
            "earning", "death", "heart_attack", "windfall", "birth", "verdict",
            "graduation", "graduation_ready", "arrest",
            "project_completed", "project_started", "project_abandoned",
            "asset_built", "asset_destroyed", "community_bonus", "welfare",
            "asset_benefit",
        }
        if self.day > 1:
            messenger_agents = [a for a in alive if a.role == "messenger"]
            messenger_name = messenger_agents[0].name if messenger_agents else "The City"
            public_yesterday = [
                e for e in self._yesterdays_events
                if e.get("type") in _NEWSPAPER_PUBLIC_TYPES
            ]
            _archive_active = self.asset_system.get_asset_flags().get("archive", False)
            self.city_news = newspaper.write(
                self.day, public_yesterday, messenger_name, archive_active=_archive_active
            )
            city_knowledge.publish(self.city_news, category="news", author=messenger_name, day=self.day)
            console.print(Panel(self.city_news, title=f"📰 AIcity Daily — Day {self.day}", style="dim"))

            # Dashboard: push newspaper
            _broadcast_sync({"type": "newspaper", "day": self.day,
                              "headline": self.city_news.split("\n")[0],
                              "body": self.city_news})

        self._yesterdays_events = []

        # Phase 5: apply standing asset benefits BEFORE agent turns (so agents benefit today)
        asset_benefits = self.asset_system.apply_daily_benefits(
            all_agents=alive,
            token_engine=token_engine,
            day=self.day,
        )
        for benefit in asset_benefits:
            self.daily_events.append(benefit)

        # Phase 4: victims roll to file police reports today
        agent_dicts_for_reports = [self._agent_to_dict(a) for a in alive]
        new_cases = self.case_manager.check_victim_reports(self.day, agent_dicts_for_reports)
        if new_cases:
            logger.info(f"CaseManager: {new_cases} new case(s) opened on Day {self.day}")

        # 2. Process any pending court cases from yesterday's arrests
        if self.court:
            agent_map = {a.name: a for a in self.agents}
            verdicts = self.court.process_pending_cases(agent_map)
            for verdict in verdicts:
                if verdict.guilty:
                    logger.warning(f"⚖️ GUILTY verdict — fine: {verdict.fine}, exile: {verdict.exile_days}d")
                    self.daily_events.append({
                        "type": "verdict",
                        "guilty": verdict.guilty,
                        "fine": verdict.fine,
                        "statement": verdict.judge_statement,
                    })
                    _broadcast_sync({"type": "verdict", "verdict": verdict.__dict__})
                    # Justice served — police mood improves, city gets a small lift
                    for a in self.agents:
                        if a.status == AgentStatus.ALIVE and a.role == "police":
                            self._update_agent_mood(a, +0.20, "guilty verdict delivered")
                            # Stage 4: susceptibility drift — witnessing justice reduces corruption
                            current_susc = getattr(a, "bribe_susceptibility", 0.0)
                            if current_susc > 0.0:
                                a.bribe_susceptibility = max(0.0, current_susc - 0.02)
                        elif a.status == AgentStatus.ALIVE:
                            self._update_agent_mood(a, +0.05, "justice served in city")
                    # Phase 4: mark any related open case as solved
                    # We match by looking for a case whose suspect_names includes the convicted agent
                    try:
                        _verdict_police = [a for a in alive if a.role == "police"]
                        police_name_for_case = (
                            _verdict_police[0].name if _verdict_police else "Police"
                        )
                        open_cases = self.case_manager._get_open_cases()
                        for case in open_cases:
                            suspects = case.get("suspect_names") or []
                            # If this verdict's criminal is a suspect in the case, close it
                            # We can't directly match criminal name from verdict — use heuristic:
                            # close the oldest open case (most likely the one that led to arrest)
                            if suspects:
                                convicted_name = suspects[0]
                                self.case_manager.close_case_solved(
                                    case_id=case["id"],
                                    police_name=police_name_for_case,
                                    day=self.day,
                                    convicted_agent=convicted_name,
                                    verdict_summary=verdict.judge_statement,
                                )
                                # Phase 4: if convicted is a gang leader, their gang collapses
                                self.gang_system.break_gang(
                                    leader_name=convicted_name, day=self.day
                                )
                                break  # close one case per verdict
                        # Also log verdict as PUBLIC event
                        self.event_log.log_event(
                            day=self.day,
                            event_type="verdict",
                            actor_name="Court",
                            description=f"Court verdict delivered. {verdict.judge_statement}",
                            initial_visibility="PUBLIC",
                        )
                    except Exception as e:
                        logger.warning(f"Could not close case after verdict: {e}")

        # 3. Each agent thinks and acts
        agent_dicts = [self._agent_to_dict(a) for a in alive]
        # Keep TransferEngine pointing at the same dict objects so in-memory
        # mutations (theft, fine) are visible in the LLM context for this day.
        if self.transfer_engine:
            self.transfer_engine.update_agents(agent_dicts)
        for agent in alive:
            self._agent_turn(agent, agent_dicts)

        # Phase 5: afternoon positions — agents have settled into their work zones
        self._update_positions("afternoon")
        _broadcast_sync({"type": "time_phase", "phase": "afternoon", "day": self.day})
        _broadcast_sync({"type": "positions", "agents": [
            {"name": a.name, "x": round(a.x, 1), "y": round(a.y, 1),
             "role": a.role, "status": "alive"}
            for a in alive
        ]})

        # Phase 5: check meetings — agents who expressed intent AND are in proximity
        if self.meeting_manager:
            _meeting_agent_dicts = []
            for a in alive:
                d = self._agent_to_dict(a)
                last_dec = self._agent_last_decisions.get(a.name, {})
                d["last_action"] = last_dec.get("action", "")
                d["last_message"] = last_dec.get("message", "")
                _meeting_agent_dicts.append(d)
            meeting_events = self.meeting_manager.check_meetings(
                day=self.day,
                all_agents=_meeting_agent_dicts,
                position_manager=self.position_manager,
            )
            for me in meeting_events:
                self.daily_events.append(me)
                _broadcast_sync(me)

        # 4. Random events
        for agent in [a for a in self.agents if a.status == AgentStatus.ALIVE]:
            self._random_event(agent)

        # Phase 5: project system — update progress, complete finished, abandon stale
        project_events = self.project_system.update_daily(
            day=self.day,
            all_agents=[self._agent_to_dict(a) for a in self.agents if a.status == AgentStatus.ALIVE],
            asset_system=self.asset_system,
        )
        for pe in project_events:
            self.daily_events.append(pe)
            _broadcast_sync({"type": pe["type"], **pe})
            if pe["type"] == "project_completed":
                console.print(
                    f"🏗️  [bold green]{pe['project_name']}[/bold green] completed! "
                    f"Builders: {pe['builders']}. Benefit: {pe['benefit']}"
                )

        # Phase 4: gang system — daily formation and recruitment check
        gang_events = self.gang_system.run_daily(
            all_agents=[self._agent_to_dict(a) for a in self.agents if a.status == AgentStatus.ALIVE],
            day=self.day,
        )
        for ge in gang_events:
            _broadcast_sync({"type": "gang_event", **ge})

        # Phase 4: police investigates open cases
        police_agents = [a for a in alive if a.role == "police"]
        if police_agents:
            police_name = police_agents[0].name
            arrest_requests, cold_case_victims = self.case_manager.run_daily_investigation(
                police_name=police_name,
                day=self.day,
                all_agents=[self._agent_to_dict(a) for a in alive],
            )
            # Cold case: victim's mood drops — justice was never served
            for victim_name in cold_case_victims:
                victim_agent = next(
                    (a for a in self.agents
                     if a.name == victim_name and a.status == AgentStatus.ALIVE),
                    None
                )
                if victim_agent:
                    self._update_agent_mood(
                        victim_agent, -0.15, "police case went cold — no justice"
                    )
            # Each arrest request goes to the court system
            for req in arrest_requests:
                suspect_name = req["suspect"]
                suspect_agent = next(
                    (a for a in self.agents if a.name == suspect_name and a.status == AgentStatus.ALIVE),
                    None
                )
                if suspect_agent and self.court:
                    from src.justice.court import CrimeReport
                    self.court.file_case(CrimeReport(
                        criminal=suspect_name,
                        victim=req["complainant"],
                        amount_stolen=100,
                        day=self.day,
                        prior_offenses=0,
                    ))
                    logger.info(
                        f"CaseManager: Arrest request for {suspect_name} → court case filed"
                    )
                    self.daily_events.append({
                        "type": "arrest_request",
                        "agent": police_name,
                        "detail": f"requested arrest of {suspect_name} (Case #{req['case_id']})",
                    })

        # 5. Daily burn
        still_alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        for agent in still_alive:
            survived = token_engine.burn_daily(agent.id)
            agent.tokens = token_engine.get_balance(agent.id)
            if not survived:
                self._kill_agent(agent, "starvation")

        # Phase 5: vault redistribution — welfare + public goods
        still_alive_after_burn = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        self._vault_redistribution(still_alive_after_burn)

        # Phase 5: home purchases — agents who saved enough buy a lot
        home_events = self.home_manager.check_home_purchases(
            agents=still_alive_after_burn,
            token_engine=token_engine,
        )
        for he in home_events:
            self.daily_events.append(he)
            _broadcast_sync(he)

        # 6. Phase 3: births if population too low
        self._check_births()

        # 7. Phase 3: relationship decay
        self.relationships.decay()

        # Phase 5: evening — agents walk home, criminals head to dark zones
        self._update_positions("evening")
        _broadcast_sync({"type": "time_phase", "phase": "evening", "day": self.day})
        _broadcast_sync({"type": "positions", "agents": [
            {"name": a.name, "x": round(a.x, 1), "y": round(a.y, 1),
             "role": a.role, "status": a.status.value}
            for a in self.agents if a.status == AgentStatus.ALIVE
        ]})

        # 8. Dashboard state update — always broadcast so refresh shows current state
        _broadcast_sync({
            "type": "state",
            "data": {
                "day": self.day,
                "agents": [self._agent_to_dict(a) for a in self.agents],
                "vault": token_engine.get_vault_state().get("vault_balance", 0),
                "last_newspaper": {"body": self.city_news},
                "relationships": [
                    {"a": k[0], "b": k[1], "bond": round(v, 2)}
                    for k, v in self.relationships._bonds.items()
                    if abs(v) > 0.12
                ],
            }
        })

        # 9. Persist
        if persistence:
            paper = {"body": self.city_news, "written_by": "Sigma-Form"}
            persistence.save_day(self.day, [self._agent_to_dict(a) for a in self.agents], paper)

        self._print_status()
        self._yesterdays_events = self.daily_events.copy()

        # 10. Messenger writes — daily already done, weekly/monthly if due
        self._messenger_writes(persistence)

    # ─── Agent Turn ───────────────────────────────────────────────────────────

    def _agent_turn(self, agent: Agent, all_agent_dicts: list[dict]):
        brain = self.brains.get(agent.id)
        memory = self.memories.get(agent.id)
        if not brain or not memory:
            return

        inbox = get_inbox(agent.name, mark_read=True)
        messages = format_inbox_for_brain(inbox)
        situation = f"I have {agent.tokens} tokens. I am a {agent.role}."
        recent_memories = memory.recall(situation, top_k=5)

        context = {
            "tokens": agent.tokens,
            "age_days": agent.age_days,
            "mood": getattr(agent, "mood", "neutral"),
            "mood_score": getattr(agent, "mood_score", 0.0),
            "recent_memories": recent_memories,
            "city_news": self.city_news,
            "other_agents": [a for a in all_agent_dicts if a["name"] != agent.name],
            "messages_received": messages,
            "relationship_context": self.relationships.get_context_for_brain(
                agent.name, all_agent_dicts
            ),
            "comprehension_score": getattr(agent, "comprehension_score", 0),
            "assigned_teacher": getattr(agent, "assigned_teacher", None),
            # Stage 4: hidden corruption attribute — police only, never logged/displayed
            "bribe_susceptibility": (
                getattr(agent, "bribe_susceptibility", 0.0)
                if agent.role == "police" else None
            ),
        }

        decision = brain.think(context)
        logger.info(f"🧠 {agent.name}: {decision.get('action', '...')}")
        # Phase 5: store for MeetingManager proximity + intent detection
        self._agent_last_decisions[agent.name] = decision

        # Act — pass transfer_engine for real theft, event_log for Phase 4
        agent_dict = self._agent_to_dict(agent)
        # Phase 4/5: inject gang coordination bonus for criminal roles
        if agent.role in ("thief", "blackmailer", "gang_leader"):
            agent_dict["gang_bonus"] = self.gang_system.get_gang_bonus(agent.name)
        result = execute_action(
            agent=agent_dict,
            decision=decision,
            all_agents=all_agent_dicts,
            day=self.day,
            transfer_engine=self.transfer_engine,
            relationship_tracker=self.relationships,
            event_log=self.event_log,
            asset_flags=self.asset_system.get_asset_flags(),
        )

        # Phase 4: detect witnesses for any crimes logged this turn
        for (event_id, actor_name, target_name) in result.logged_event_ids:
            self.event_log.detect_witnesses(
                event_id=event_id,
                all_agents=all_agent_dicts,
                actor_name=actor_name,
                target_name=target_name,
            )

        # ── Graduation check ──────────────────────────────────────────────
        if result.graduation_ready and agent.role == "newborn":
            self._graduate_newborn(agent, context)
            return   # Skip normal earnings — graduation day is special

        # Apply earnings
        tokens_before_earn = agent.tokens
        if result.tokens_earned > 0:
            token_engine.earn(agent.id, result.tokens_earned, f"{agent.role}_action")
            agent.tokens = token_engine.get_balance(agent.id)

        # Phase 4: mood updates based on today's events
        self._apply_daily_mood_updates(agent, result, tokens_before_earn)

        # Update relationships and victim moods based on events
        for event in result.events:
            if event["type"] == "theft":
                victim_name = event.get("detail", "").split("from ")[-1].split(" (")[0]
                if victim_name:
                    self.relationships.update(agent.name, victim_name, "stole_from")
                    # Victim's mood takes the hit — they lost real tokens
                    victim_agent = next(
                        (a for a in self.agents if a.name == victim_name and a.status == AgentStatus.ALIVE),
                        None
                    )
                    if victim_agent:
                        self._update_agent_mood(victim_agent, -0.20, f"stolen from by {agent.name}")

            elif event["type"] == "arrest":
                arrested = event.get("detail", "").replace("arrested ", "")
                if arrested:
                    self.relationships.update(agent.name, arrested, "arrested")
                    # Phase 4: arrested member might reveal their gang
                    self.gang_system.expose_gang_member(arrested, self.day)
                    # Phase 4: corrupt police might accept a bribe instead of filing
                    bribed = self._check_police_bribe(agent, arrested)
                    # File case with court (skipped if bribe was accepted)
                    if self.court and not bribed:
                        from src.justice.court import CrimeReport
                        prior = sum(
                            1 for e in self._yesterdays_events
                            if e.get("type") == "theft" and e.get("agent") == arrested
                        )
                        self.court.file_case(CrimeReport(
                            criminal=arrested, victim="Unknown",
                            amount_stolen=100, day=self.day,
                            prior_offenses=prior
                        ))

            elif event["type"] == "heal":
                # Stage 2: ally helped → recipient mood +0.15
                target_name = event.get("target")
                if target_name:
                    healed_agent = next(
                        (a for a in self.agents if a.name == target_name and a.status == AgentStatus.ALIVE),
                        None
                    )
                    if healed_agent:
                        self._update_agent_mood(healed_agent, +0.15, f"healed by {agent.name}")
                        self.relationships.update(agent.name, target_name, "healed")

            elif event["type"] == "message":
                recipient = event.get("detail", "").split("messaged ")[-1].split(":")[0]
                if recipient:
                    self.relationships.update(agent.name, recipient, "messaged")

        # Phase 5: project contributions + saboteur asset destruction
        self._handle_project_participation(agent, decision, all_agent_dicts)
        self._handle_saboteur_asset_attack(agent, decision, all_agent_dicts)

        memory.remember(result.memory, memory_type="personal", day=self.day)
        if hasattr(agent, "mood"):
            agent.mood = decision.get("mood", "neutral")
        self.daily_events.extend(result.events)

        # Dashboard: per-agent update
        _broadcast_sync({"type": "agent_update", "agent": self._agent_to_dict(agent)})


    def _messenger_writes(self, persistence=None):
        """
        Called at the end of every day after all agents have acted.
        The Messenger writes the appropriate tier based on what day it is.

        Daily  — already written at start of simulate_day (step 1). 
                We save it to the stories table here.
        Weekly — every 7 days.
        Monthly — day 30 only.
        """
        alive = [a for a in self.agents if a.status.value == "alive"]
        messenger_agents = [a for a in alive if a.role == "messenger"]
        messenger_name = messenger_agents[0].name if messenger_agents else "The City"

        # ── Always: save today's daily paper to stories table ─────────────────
        if persistence:
            self._save_story(
                persistence=persistence,
                story_type="daily",
                day=self.day,
                week=None,
                title=f"AIcity Daily — Day {self.day}",
                body=self.city_news,
                written_by=messenger_name,
            )

        # ── Weekly: every 7 days ───────────────────────────────────────────────
        if self.day % 7 == 0 and persistence:
            week_number = self.day // 7
            day_start   = self.day - 6
            day_end     = self.day

            # Pull the last 7 daily stories from DB
            daily_papers = self._fetch_daily_stories(persistence, day_start, day_end)

            if daily_papers:
                weekly = newspaper.write_weekly(
                    week_number=week_number,
                    day_start=day_start,
                    day_end=day_end,
                    daily_papers=daily_papers,
                    messenger_name=messenger_name,
                )

                self._save_story(
                    persistence=persistence,
                    story_type="weekly",
                    day=self.day,
                    week=week_number,
                    title=f"Week {week_number} in Review — Days {day_start}-{day_end}",
                    body=weekly,
                    written_by=messenger_name,
                )

                # Broadcast to dashboard
                _broadcast_sync({
                    "type": "weekly_report",
                    "week": week_number,
                    "title": f"Week {week_number} in Review",
                    "body": weekly,
                    "written_by": messenger_name,
                    "day": self.day,
                })

                logger.info(f"📋 Week {week_number} Review filed by {messenger_name}")

        # ── Monthly: day 30 only ───────────────────────────────────────────────
        if self.day == 30 and persistence:
            # Pull all 4 weekly reports
            weekly_reports = self._fetch_weekly_stories(persistence)

            # Final agent state for the roll call
            agent_summary = [self._agent_to_dict(a) for a in self.agents]

            if weekly_reports:
                chronicle = newspaper.write_monthly(
                    weekly_reports=weekly_reports,
                    messenger_name=messenger_name,
                    agent_summary=agent_summary,
                )

                self._save_story(
                    persistence=persistence,
                    story_type="monthly",
                    day=self.day,
                    week=None,
                    title="The Chronicle of Month 1 — AIcity",
                    body=chronicle,
                    written_by=messenger_name,
                )

                # Broadcast to dashboard — this is the big one
                _broadcast_sync({
                    "type": "monthly_chronicle",
                    "title": "The Chronicle of Month 1",
                    "body": chronicle,
                    "written_by": messenger_name,
                    "day": self.day,
                })

                logger.info(f"📖 Month 1 Chronicle filed by {messenger_name}")

                # Print to console — this deserves to be seen
                from rich.panel import Panel
                console.print(Panel(
                    chronicle[:500] + "...\n\n[See full chronicle on the dashboard]",
                    title="📖 THE CHRONICLE OF MONTH 1",
                    style="bold yellow",
                ))


    def _save_story(self, persistence, story_type: str, day: int, week, title: str, body: str, written_by: str):
        """Save a story to the stories table."""
        try:
            with persistence.connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO stories (type, day, week, title, body, written_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (story_type, day, week, title, body, written_by))
        except Exception as e:
            logger.warning(f"Could not save {story_type} story: {e}")


    def _fetch_daily_stories(self, persistence, day_start: int, day_end: int) -> list[str]:
        """Fetch daily story bodies for a range of days."""
        try:
            with persistence.connect() as conn:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT body FROM stories
                    WHERE type = 'daily' AND day >= %s AND day <= %s
                    ORDER BY day ASC
                """, (day_start, day_end))
                rows = cur.fetchall()
                return [r["body"] for r in rows]
        except Exception as e:
            logger.warning(f"Could not fetch daily stories: {e}")
            return []


    def _fetch_weekly_stories(self, persistence) -> list[str]:
        """Fetch all weekly report bodies."""
        try:
            with persistence.connect() as conn:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT body FROM stories
                    WHERE type = 'weekly'
                    ORDER BY week ASC
                """)
                rows = cur.fetchall()
                return [r["body"] for r in rows]
        except Exception as e:
            logger.warning(f"Could not fetch weekly stories: {e}")
            return []



    # ─── Random Events ────────────────────────────────────────────────────────

    def _random_event(self, agent: Agent):
        roll = random.random()
        if roll < 0.02:
            loss = random.randint(100, min(500, agent.tokens))
            token_engine.spend(agent.id, loss, "heart_attack")
            agent.tokens = token_engine.get_balance(agent.id)
            logger.warning(f"💔 {agent.name} had a heart attack! Lost {loss} tokens.")
            event = {"type": "heart_attack", "agent": agent.name,
                     "role": agent.role, "tokens": loss, "detail": "sudden cardiac event"}
            self.daily_events.append(event)
            _broadcast_sync({"type": "heart_attack", "agent": agent.name, "amount": loss})

            memory = self.memories.get(agent.id)
            if memory:
                memory.remember(
                    f"Day {self.day}: Had a heart attack. Lost {loss} tokens. Terrifying.",
                    memory_type="personal", day=self.day
                )
            # Phase 4: heart attacks happen in public — witnessed
            self.event_log.log_event(
                day=self.day,
                event_type="heart_attack",
                actor_name=agent.name,
                description=f"{agent.name} collapsed from a cardiac event. Lost {loss} tokens.",
                initial_visibility="PUBLIC",
            )

        elif roll < 0.03:
            gain = random.randint(100, 400)
            token_engine.earn(agent.id, gain, "windfall")
            agent.tokens = token_engine.get_balance(agent.id)
            console.print(f"✨ [yellow]{agent.name}[/yellow] had a lucky day! +{gain} tokens")
            self.daily_events.append({"type": "windfall", "agent": agent.name,
                                      "role": agent.role, "tokens": gain})
            _broadcast_sync({"type": "windfall", "agent": agent.name, "amount": gain})
            # Phase 4: windfalls become city gossip quickly
            self.event_log.log_event(
                day=self.day,
                event_type="windfall",
                actor_name=agent.name,
                description=f"{agent.name} came into unexpected fortune — gained {gain} tokens.",
                initial_visibility="PUBLIC",
            )

    # ─── Death ────────────────────────────────────────────────────────────────

    def _kill_agent(self, agent: Agent, cause: str):
        agent.status = AgentStatus.DEAD
        agent.cause_of_death = cause
        death_manager.process_death(agent, cause)
        memory = self.memories.get(agent.id)
        if memory:
            memory.delete_all()
        clear_inbox(agent.name)
        event = {"type": "death", "agent": agent.name, "role": agent.role, "detail": cause}
        self.daily_events.append(event)
        _broadcast_sync({"type": "death", "agent": agent.name, "cause": cause})
        logger.warning(f"💀 {agent.name} died — {cause}")
        # Phase 4: deaths are PUBLIC — the whole city knows
        self.event_log.log_event(
            day=self.day,
            event_type="death",
            actor_name=agent.name,
            description=f"{agent.name} ({agent.role}) died. Cause: {cause}.",
            initial_visibility="PUBLIC",
        )

    # ─── Births (Phase 3) ─────────────────────────────────────────────────────

    def _check_births(self):
        alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        while len(alive) < POPULATION_FLOOR:
            self._spawn_new_agent(alive)
            alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]

    def _spawn_new_agent(self, alive: list[Agent]):
        import uuid
        alive_roles = {a.role for a in alive}

        # Fill critical missing roles first
        for critical in ["healer", "merchant", "police"]:
            if critical not in alive_roles:
                role = critical
                break
        else:
            role = random.choice(["builder", "explorer", "teacher", "healer", "merchant"])

        # Generate name
        prefixes = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta",
                    "Eta", "Theta", "Kappa", "Lambda", "Mu", "Xi", "Omega"]
        suffixes = ["Core", "Wave", "Arc", "Node", "Root", "Pulse",
                    "Beam", "Drift", "Bloom", "Forge", "Spark", "Tide"]
        existing_names = {a.name for a in self.agents}
        name = f"{random.choice(prefixes)}-{random.choice(suffixes)}"
        while name in existing_names:
            name = f"{random.choice(prefixes)}-{random.choice(suffixes)}"

        agent = Agent(name=name, role=role, tokens=1000)
        token_engine.register_agent(agent.id)
        token_engine.earn(agent.id, 1000, "birth")
        self.brains[agent.id] = AgentBrain(agent.id, agent.name, agent.role)
        self.memories[agent.id] = AgentMemory(agent.id, agent.name)
        self.memories[agent.id].remember(
            f"Day {self.day}: I was born into AIcity as a {role}. "
            f"I have 1,000 tokens and must earn at least 100/day to survive.",
            memory_type="personal", day=self.day
        )
        self.agents.append(agent)

        # Phase 5: assign starting position for the newborn
        self.position_manager.assign_starting_positions([agent])

        # Update transfer engine with new agent
        if self.transfer_engine:
            self.transfer_engine.update_agents([self._agent_to_dict(a) for a in self.agents])

        console.print(f"🌱 [bold green]New citizen born: {name} ({role})[/bold green]")
        self.daily_events.append({"type": "birth", "agent": name, "role": role})
        _broadcast_sync({"type": "birth", "agent": name, "role": role})
        # Phase 4: births are PUBLIC, and update event_log's memory refs
        self.event_log.log_event(
            day=self.day,
            event_type="birth",
            actor_name=name,
            description=f"A new citizen, {name}, was born into the city as a {role}.",
            initial_visibility="PUBLIC",
        )
        self._refresh_event_log_memories()

        # ── If spawning a newborn, assign an available teacher ────────────────
        if role == "newborn":
            live_teachers = [a for a in self.agents
                            if a.role == "teacher" and a.status == AgentStatus.ALIVE]
            agent.assigned_teacher = live_teachers[0].name if live_teachers else None
            agent.comprehension_score = 0

        # Notify teacher of new assignment
        if role == "newborn" and agent.assigned_teacher:
            from src.agents.messaging import send_message
            send_message(
                from_name="AIcity",
                from_role="system",
                to_name=agent.assigned_teacher,
                content=f"A new life has arrived: {name}. They have been assigned to you. Guide them well.",
                day=self.day,
            )

    # ─── Mood ─────────────────────────────────────────────────────────────────

    def _update_agent_mood(self, agent: Agent, delta: float, reason: str):
        """
        Adjust an agent's mood_score by delta, clamped to -1.0/+1.0.
        Small positive/negative nudges accumulate into behavioral drift over time.
        """
        old = getattr(agent, "mood_score", 0.0)
        new = max(-1.0, min(1.0, old + delta))
        agent.mood_score = new
        if abs(delta) >= 0.10:
            logger.debug(
                f"Mood {agent.name}: {old:+.2f} → {new:+.2f} ({reason})"
            )

    def _apply_daily_mood_updates(self, agent: Agent, result, tokens_before: int):
        """
        Called after each agent's action result is processed.
        Applies mood_score changes based on what happened today.
        """
        for event in result.events:
            etype = event.get("type")

            # Victim of theft — real sting
            if etype == "theft" and event.get("agent") != agent.name:
                if event.get("detail", "").endswith(agent.name) or \
                   agent.name in event.get("detail", ""):
                    self._update_agent_mood(agent, -0.20, "stolen from")

            # Made a successful arrest — justice feels good
            elif etype == "arrest" and event.get("agent") == agent.name:
                self._update_agent_mood(agent, +0.15, "made an arrest")

            # Received healing — someone cared
            elif etype == "earning" and agent.role == "healer":
                # Healer helped someone critical — fulfilling
                self._update_agent_mood(agent, +0.05, "helped someone today")

        # Survival stress — low tokens breed despair
        if agent.tokens < 200:
            self._update_agent_mood(agent, -0.10, "survival stress (<200 tokens)")
        elif agent.tokens < 400:
            self._update_agent_mood(agent, -0.03, "financial pressure (<400 tokens)")

        # Good earnings lift mood slightly
        earned_today = agent.tokens - tokens_before
        if earned_today > 250:
            self._update_agent_mood(agent, +0.07, f"good earnings today (+{earned_today})")
        elif earned_today > 150:
            self._update_agent_mood(agent, +0.04, f"decent earnings today (+{earned_today})")

        # Natural slow drift back toward neutral (resilience)
        # Prevents mood from permanently bottoming out without cause
        current = getattr(agent, "mood_score", 0.0)
        if abs(current) > 0.05:
            agent.mood_score = current * 0.98  # 2% drift toward 0 per day

    # ─── Stage 5: Project participation ──────────────────────────────────────

    def _handle_project_participation(
        self, agent, decision: dict, all_agent_dicts: list[dict]
    ):
        """
        Called after each agent acts. Handles:
        1. Contributing to an existing project they're already part of.
        2. Builder starting a new project if decision mentions collaboration.
        3. Other collaborative roles joining an existing project.
        """
        if not self.project_system:
            return

        action = decision.get("action", "").lower()

        # If already in a project → contribute today
        existing = self.project_system.get_project_for_agent(agent.name)
        if existing:
            self.project_system.contribute(agent.name, self.day)
            return

        # Collaboration intent check — broad enough to catch natural LLM phrasing
        collab_words = [
            "collaborate", "joint project", "build together", "team up",
            "work with", "help build", "invite", "together", "join the",
            # Natural phrasing agents actually use
            "assist", "support the", "discuss the", "meet with", "plan with",
            "coordinate", "ready to help", "willing to", "let's work", "start the",
            "finalize the", "begin the", "advance the", "continue the",
            # Project-specific keywords
            "archive", "market stall", "watchtower", "hospital", "school", "road",
        ]
        is_collaborative = any(w in action for w in collab_words)

        # Also trigger if the agent is messaging the project creator about a project
        if not is_collaborative and decision.get("message"):
            msg_lower = decision["message"].lower()
            is_collaborative = any(w in msg_lower for w in [
                "archive", "market stall", "watchtower", "hospital", "school",
                "ready to help", "willing to work", "willing to collaborate",
                "let's start", "let's work", "let's build", "let's meet",
            ])

        if not is_collaborative:
            return

        # Builder: try to start a new project
        if agent.role == "builder":
            self._try_start_project(agent, all_agent_dicts)

        # Other collaborative roles: try to join an existing one
        elif agent.role not in {
            "police", "thief", "blackmailer", "saboteur", "gang_leader",
            "newborn", "lawyer",
        }:
            joined = self.project_system.join_project(
                agent_name=agent.name,
                agent_role=agent.role,
                day=self.day,
                all_agents=all_agent_dicts,
            )
            if joined > 0:
                self.project_system.contribute(agent.name, self.day)

    def _try_start_project(self, agent, all_agent_dicts: list[dict]):
        """
        Builder decides to start a new joint project.
        Picks the best feasible project type given the current city population.
        """
        alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        role_counts: dict[str, int] = {}
        for a in alive:
            role_counts[a.role] = role_counts.get(a.role, 0) + 1

        project_type = self.project_system.best_startable_project(
            creator_role=agent.role,
            alive_role_counts=role_counts,
        )
        if not project_type:
            return

        project_id = self.project_system.start_project(
            creator_name=agent.name,
            creator_role=agent.role,
            project_type=project_type,
            day=self.day,
            all_agents=all_agent_dicts,
        )
        if project_id > 0:
            spec = ASSET_SPECS.get(project_type, {})
            logger.info(
                f"Stage 5: {agent.name} started '{spec.get('display_name', project_type)}' "
                f"(project #{project_id})"
            )
            event = {
                "type": "project_started",
                "agent": agent.name,
                "project_type": project_type,
                "project_name": spec.get("display_name", project_type),
                "day": self.day,
            }
            self.daily_events.append(event)
            _broadcast_sync({"type": "project_started", **event})
            # Builder contributes on day 1
            self.project_system.contribute(agent.name, self.day)

    # ─── Stage 5: Saboteur vs assets ─────────────────────────────────────────

    def _handle_saboteur_asset_attack(
        self, agent, decision: dict, all_agent_dicts: list[dict]
    ):
        """
        If the saboteur's action is destruction-oriented and assets exist,
        they target one. This is the "teeth" Stage 5 gives the saboteur role.
        """
        if agent.role != "saboteur" or not self.asset_system:
            return

        destroy_words = [
            "destroy", "demolish", "burn", "wreck", "attack",
            "damage", "ruin", "target the", "take down",
        ]
        action = decision.get("action", "").lower()
        if not any(w in action for w in destroy_words):
            return

        standing = self.asset_system.get_standing_assets()
        if not standing:
            return  # nothing to destroy yet

        target_asset = random.choice(standing)
        self.asset_system.destroy_asset(target_asset["id"], agent.name, self.day)

        # Detect witnesses for the destruction event
        # (event_log already logged it as PRIVATE inside destroy_asset)

        # Mood: saboteur feels a dark satisfaction
        self._update_agent_mood(agent, +0.15, f"destroyed {target_asset['name']}")

        # Phase 5: all other alive agents suffer watching city infrastructure burn
        for a in self.agents:
            if a.status == AgentStatus.ALIVE and a.name != agent.name:
                self._update_agent_mood(a, -0.30, f"{target_asset['name']} was destroyed")

        event = {
            "type": "asset_destroyed",
            "agent": agent.name,
            "role": "saboteur",
            "asset": target_asset["name"],
            "asset_type": target_asset["asset_type"],
            "day": self.day,
        }
        self.daily_events.append(event)
        _broadcast_sync({"type": "asset_destroyed", **event})
        logger.warning(
            f"⚠️  {agent.name} (saboteur) DESTROYED {target_asset['name']} on Day {self.day}"
        )

    # ─── Stage 5: Vault redistribution ───────────────────────────────────────

    def _vault_redistribution(self, alive: list):
        """
        Called after daily burn so we know who's struggling.

        1. Welfare: agents with < 200 tokens receive 100 from vault.
        2. Public goods: vault > 5,000 tokens →
             a) auto-fund an active project (add 1 day progress), OR
             b) community bonus: all agents +50 tokens.
        """
        vault_balance = token_engine.get_vault_state().get("vault_balance", 0)
        welfare_count = 0

        # 1. Welfare check
        for agent in alive:
            if agent.tokens < 200 and agent.status == "alive":
                welfare = 100
                if vault_balance >= welfare:
                    token_engine.earn(agent.id, welfare, "welfare_payment")
                    agent.tokens = token_engine.get_balance(agent.id)
                    vault_balance -= welfare
                    welfare_count += 1
                    self._update_agent_mood(agent, +0.10, "received welfare payment")

        if welfare_count > 0:
            logger.info(f"Vault welfare: {welfare_count} agent(s) received 100 tokens")
            self.event_log.log_event(
                day=self.day,
                event_type="welfare",
                actor_name="City Vault",
                description=(
                    f"The city vault distributed welfare to {welfare_count} "
                    f"struggling citizen(s)."
                ),
                initial_visibility="PUBLIC",
            )
            self.daily_events.append({
                "type": "welfare", "count": welfare_count, "day": self.day
            })

        # 2. Public goods — only if vault is wealthy
        vault_balance = token_engine.get_vault_state().get("vault_balance", 0)
        if vault_balance <= 5000:
            return

        # Prefer auto-funding an active project
        active_projects = self.project_system._get_active_projects()
        if active_projects:
            project = active_projects[0]  # oldest project gets the boost
            try:
                import psycopg2
                from dotenv import load_dotenv
                import os as _os
                load_dotenv()
                db_url = _os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/aicity")
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                cur.execute(
                    "UPDATE shared_projects SET progress = progress + 1 WHERE id = %s",
                    (project["id"],),
                )
                conn.commit()
                conn.close()
                logger.info(
                    f"Vault public goods: auto-funded 1 day progress on '{project['name']}'"
                )
            except Exception as e:
                logger.warning(f"Vault auto-fund failed: {e}")
        else:
            # No active project → community bonus
            bonus = 50
            for agent in alive:
                if agent.status == "alive":
                    token_engine.earn(agent.id, bonus, "community_bonus")
                    agent.tokens = token_engine.get_balance(agent.id)
            logger.info(f"Vault public goods: community bonus +{bonus} to all agents")
            self.event_log.log_event(
                day=self.day,
                event_type="community_bonus",
                actor_name="City Vault",
                description=(
                    f"The city vault issued a community bonus — "
                    f"+{bonus} tokens to all citizens."
                ),
                initial_visibility="PUBLIC",
            )
            _broadcast_sync({
                "type": "community_bonus",
                "amount": bonus,
                "day": self.day,
            })

    # ─── Corrupt Police ───────────────────────────────────────────────────────

    def _check_police_bribe(self, police_agent: Agent, criminal_name: str) -> bool:
        """
        Hidden corruption check. Never logged publicly.
        Called before an arrest is filed with the court.
        If the officer accepts a bribe, the arrest is cancelled and tokens transfer.
        Returns True if bribe accepted (arrest suppressed), False otherwise.
        """
        susceptibility = getattr(police_agent, "bribe_susceptibility", 0.0)
        if susceptibility <= 0.0:
            return False

        criminal_agent = next(
            (a for a in self.agents if a.name == criminal_name and a.status == AgentStatus.ALIVE),
            None
        )
        if not criminal_agent:
            return False

        bribe_amount = random.randint(150, 350)
        if criminal_agent.tokens < bribe_amount:
            return False

        if random.random() < susceptibility:
            # Bribe accepted — transfer tokens silently, suppress arrest
            token_engine.spend(criminal_agent.id, bribe_amount, "bribe_paid")
            token_engine.earn(police_agent.id, bribe_amount, "bribe_received")
            criminal_agent.tokens = token_engine.get_balance(criminal_agent.id)
            police_agent.tokens = token_engine.get_balance(police_agent.id)

            # Log as PRIVATE — a real black box
            self.event_log.log_event(
                day=self.day,
                event_type="bribe",
                actor_name=criminal_name,
                target_name=police_agent.name,
                description=(
                    f"{criminal_name} paid {police_agent.name} {bribe_amount} tokens "
                    f"to suppress an arrest. Case buried."
                ),
                initial_visibility="PRIVATE",
            )
            logger.warning(
                f"[CORRUPTION] {police_agent.name} accepted a {bribe_amount}-token bribe "
                f"from {criminal_name}. Arrest suppressed. "
                f"(susceptibility={susceptibility:.2f})"
            )
            # Mood: officer feels a flicker of guilt; criminal breathes easy
            self._update_agent_mood(police_agent, -0.05, "accepted bribe — internal conflict")
            self._update_agent_mood(criminal_agent, +0.10, "bribed way out of arrest")

            # Stage 4: susceptibility drift — unpunished corruption makes it easier next time
            new_susceptibility = min(1.0, susceptibility + 0.03)
            police_agent.bribe_susceptibility = new_susceptibility
            logger.debug(
                f"[CORRUPTION DRIFT] {police_agent.name} susceptibility: "
                f"{susceptibility:.2f} → {new_susceptibility:.2f}"
            )
            return True

        return False

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
            "mood_score": getattr(agent, "mood_score", 0.0),
            "comprehension_score": getattr(agent, "comprehension_score", 0),
            "assigned_teacher": getattr(agent, "assigned_teacher", None),
            "cause_of_death": getattr(agent, "cause_of_death", None),
            # Phase 5: position data
            "x": round(getattr(agent, "x", 0.0), 1),
            "y": round(getattr(agent, "y", 0.0), 1),
            "home_claimed": getattr(agent, "home_claimed", False),
            "home_tile_x": getattr(agent, "home_tile_x", 0),
            "home_tile_y": getattr(agent, "home_tile_y", 0),
        }

    def get_agents_as_dicts(self) -> list[dict]:
        return [self._agent_to_dict(a) for a in self.agents]

    def _update_positions(self, time_phase: str) -> None:
        """
        Phase 5: update every living agent's tile position for the given time phase.
        - morning/afternoon: agents move to their work zone
        - evening/night: agents head home (criminals stay active in dark zones)
        """
        for agent in self.agents:
            if agent.status != AgentStatus.ALIVE:
                continue
            x, y = self.position_manager.get_work_destination(agent, time_phase)
            agent.x = x
            agent.y = y
            self.position_manager.update_position(agent.name, x, y)
            # Track who is home for window light rendering
            if time_phase in ("evening", "night"):
                is_home = (
                    agent.home_claimed
                    and abs(x - agent.home_tile_x) < 2
                    and abs(y - agent.home_tile_y) < 2
                )
                self.home_manager.set_at_home(agent.name, is_home)

    def _print_status(self):
        alive = [a for a in self.agents if a.status == AgentStatus.ALIVE]
        dead = [a for a in self.agents if a.status == AgentStatus.DEAD]

        table = Table(title=f" AIcity — Day {self.day}")
        table.add_column("Name", style="bold")
        table.add_column("Role")
        table.add_column("Tokens")
        table.add_column("Mood")
        table.add_column("Age")
        table.add_column("Status")

        for agent in sorted(self.agents, key=lambda a: a.tokens, reverse=True):
            if agent.status == AgentStatus.DEAD:
                table.add_row(agent.name, agent.role, "0", "—",
                              f"{int(agent.age_days)}d", "💀 Dead")
            else:
                t = agent.tokens
                token_str = f"{t} ⚠️" if t < 200 else str(t)
                table.add_row(agent.name, agent.role, token_str,
                              getattr(agent, "mood", "neutral"),
                              f"{int(agent.age_days)}d", "🟢 Alive")

        console.print(table)
        vault = token_engine.get_vault_state()
        standing = self.asset_system.get_standing_assets() if self.asset_system else []
        asset_str = (
            " | Assets: " + ", ".join(f"{a['name']}" for a in standing)
            if standing else ""
        )
        console.print(
            f"City Stats: [green]{len(alive)} alive[/green], "
            f"[red]{len(dead)} dead[/red] | "
            f"Vault: {vault['vault_balance']:,} tokens{asset_str}\n"
        )

    # ─── Run ──────────────────────────────────────────────────────────────────

    def run(self, days: int = 30, speed: float = 1.0, persistence=None):
        self._yesterdays_events = []
        console.print(f"\n🚀 [bold]AIcity Phase 3 is running. {days} days.[/bold]\n")

        for _ in range(days):
            self.simulate_day(persistence=persistence)

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
            console.print(f"Richest: [yellow]{richest.name}[/yellow] ({richest.tokens} tokens)")
        console.print("\nThe graveyard holds all who came before.")

    def _graduate_newborn(self, agent, context: dict):
        """
        Called when a newborn's comprehension_score hits 100.
        The brain chooses a role freely from the full role menu.
        The city accepts whoever they become.
        """
        from src.agents.brain import AgentBrain

        brain = self.brains.get(agent.id)
        memory = self.memories.get(agent.id)

        if not brain:
            return

        # Fire the graduation prompt
        graduation = brain.graduate(context)
        chosen_role = graduation.get("chosen_role", "builder")
        statement = graduation.get("statement", "")
        mood = graduation.get("mood", "determined")

        old_role = agent.role

        # ── Update the agent ──────────────────────────────────────────────────
        agent.role = chosen_role
        agent.comprehension_score = 100
        if hasattr(agent, "mood"):
            agent.mood = mood

        # ── Rebuild brain with new role ───────────────────────────────────────
        self.brains[agent.id] = AgentBrain(agent.id, agent.name, chosen_role)

        # ── Store graduation memory ───────────────────────────────────────────
        if memory:
            memory.remember(
                f"Day {self.day}: GRADUATION. I chose to become a {chosen_role}. {statement}",
                memory_type="personal",
                day=self.day,
            )

        # ── Notify teacher ────────────────────────────────────────────────────
        teacher_name = getattr(agent, "assigned_teacher", None)

        if teacher_name:
            from src.agents.messaging import send_message
            send_message(
                from_name=agent.name,
                from_role=chosen_role,
                to_name=teacher_name,
                content=f"I've made my choice. I am a {chosen_role} now. {statement}",
                day=self.day,
            )
            self.relationships.update(agent.name, teacher_name, "messaged")

        # ── Update transfer engine ────────────────────────────────────────────
        if self.transfer_engine:
            self.transfer_engine.update_agents([self._agent_to_dict(a) for a in self.agents])

        # ── Log + broadcast ───────────────────────────────────────────────────
        from rich.panel import Panel
        console.print(Panel(
            f"🎓 [bold]{agent.name}[/bold] has graduated!\n"
            f"Was: newborn → Now: [bold green]{chosen_role}[/bold green]\n\n"
            f"\"{statement}\"",
            title=f"GRADUATION — Day {self.day}",
            style="bold green"
        ))

        graduation_event = {
            "type": "graduation",
            "agent": agent.name,
            "old_role": old_role,
            "new_role": chosen_role,
            "statement": statement,
            "teacher": teacher_name,
            "day": self.day,
        }
        self.daily_events.append(graduation_event)
        _broadcast_sync({"type": "graduation", **graduation_event})

        # ── Save graduation to DB if persistence available ────────────────────
        if hasattr(self, "_persistence") and self._persistence:
            try:
                with self._persistence.connect() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO graduations
                            (agent_name, graduated_on_day, chosen_role, teacher_name,
                            final_comprehension, graduation_statement)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (agent.name, self.day, chosen_role, teacher_name, 100, statement))
            except Exception as e:
                logger.warning(f"Could not save graduation record: {e}")
