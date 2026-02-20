"""
CaseManager — Phase 4, Stage 3: Police Complaint Book

Every crime that gets reported to police creates a case here.
The police officer (Claude) investigates daily, writing case notes.
Cases close as solved (after a court conviction) or cold (14 days, no leads).
On close, Claude writes a full narrative case report.

Key rules (enforced here):
- Police only sees evidence in the event_log with visibility WITNESSED, REPORTED, or PUBLIC.
- The investigation LLM prompt contains ONLY that evidence — no god-view.
- Cold cases stay in the DB. New evidence can reopen them.
- The final case report is written in the police officer's voice.
"""

import os
import json
import random

import psycopg2
import psycopg2.extras
from anthropic import Anthropic
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/aicity"
)

# How many days before an open case goes cold with no progress
COLD_CASE_DAYS = 14

# Probability that a theft victim files a formal report (per day)
VICTIM_REPORT_CHANCE = 0.60

# Confidence threshold above which police will request an arrest
ARREST_CONFIDENCE_THRESHOLD = 0.65

INVESTIGATION_SYSTEM_PROMPT = """You are a police officer in AIcity.
You investigate crimes using only the evidence available to you.
You write honest, methodical case notes. You do not speculate beyond the evidence.
You follow the 8 Laws of AIcity and pursue justice without bias.
You may be wrong. Innocent agents can be suspected. That is the nature of investigation."""


class CaseManager:
    """
    Manages the police complaint book and daily investigation cycle.

    Instantiate once in city_v3.py and pass into the daily loop.
    Requires: an EventLog instance and a police agent name.
    """

    def __init__(self, event_log):
        self.event_log = event_log
        self._client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # ─── Victim reporting ─────────────────────────────────────────────────────

    def check_victim_reports(self, day: int, all_agents: list[dict]) -> int:
        """
        Called at the start of each day.
        Victims who were notified of a crime (but haven't reported yet)
        roll a chance to file a formal report with police.

        Returns: number of new cases opened.
        """
        opened = 0
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                # Find recent theft/assault events with a known target that
                # aren't REPORTED yet (victim knows but hasn't gone to police)
                cur.execute("""
                    SELECT el.id, el.day, el.event_type, el.actor_name,
                           el.target_name, el.description, el.visibility
                    FROM event_log el
                    LEFT JOIN police_cases pc ON pc.event_log_id = el.id
                    WHERE el.event_type IN ('theft', 'assault', 'blackmail')
                      AND el.target_name IS NOT NULL
                      AND el.visibility IN ('PRIVATE', 'WITNESSED', 'RUMOR')
                      AND el.day >= %s
                      AND pc.id IS NULL
                """, (day - 3,))
                unreported = cur.fetchall()

            for event in unreported:
                target = event["target_name"]
                # Check the target is still alive
                alive = any(
                    a["name"] == target and a.get("status") == "alive"
                    for a in all_agents
                )
                if not alive:
                    continue

                # Victim rolls to report
                if random.random() < VICTIM_REPORT_CHANCE:
                    # Promote event to REPORTED
                    self.event_log.file_report(event["id"], target, day)
                    # Open a case
                    case_id = self._open_case(
                        event_log_id=event["id"],
                        day_opened=day,
                        complaint_text=(
                            f"{target} reports: something was taken from me. "
                            f"I noticed on day {event['day']}. I don't know who did it."
                        ),
                        complainant=target,
                    )
                    if case_id > 0:
                        opened += 1
                        logger.info(
                            f"CaseManager: {target} filed report → Case #{case_id} opened (Day {day})"
                        )

        except Exception as e:
            logger.warning(f"CaseManager.check_victim_reports failed: {e}")

        return opened

    # ─── Open a case ──────────────────────────────────────────────────────────

    def _open_case(
        self,
        event_log_id: int,
        day_opened: int,
        complaint_text: str,
        complainant: str,
    ) -> int:
        """Create a new case record. Returns case_id or -1 on failure."""
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO police_cases
                        (event_log_id, day_opened, complaint_text, complainant)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (event_log_id, day_opened, complaint_text, complainant))
                return cur.fetchone()[0]
        except Exception as e:
            logger.warning(f"CaseManager._open_case failed: {e}")
            return -1

    # ─── Daily investigation ──────────────────────────────────────────────────

    def run_daily_investigation(
        self,
        police_name: str,
        day: int,
        all_agents: list[dict],
    ) -> tuple[list[dict], list[str]]:
        """
        Called once per day, after the police agent has taken their turn.
        Police investigates all open cases using available evidence.
        Returns (arrest_requests, cold_case_victims):
          - arrest_requests: [{case_id, suspect, reason}]
          - cold_case_victims: list of complainant names whose cases went cold today

        The LLM (Claude) only sees evidence that EXISTS in the DB.
        No god-view. Police may be wrong.
        """
        open_cases = self._get_open_cases()
        arrest_requests = []
        cold_case_victims = []

        for case in open_cases:
            # Check if case should go cold
            days_open = day - case["day_opened"]
            if days_open >= COLD_CASE_DAYS:
                self._close_case_cold(case, police_name, day)
                cold_case_victims.append(case["complainant"])
                continue

            # Gather all evidence the police can see
            evidence = self.event_log.get_evidence_for_police(
                target_name=case["complainant"],
                since_day=case["day_opened"] - 1,
            )

            # Build and fire the investigation prompt
            prompt = self._build_investigation_prompt(
                police_name, case, evidence, all_agents, day
            )
            result = self._call_police_llm(prompt)

            if not result:
                continue

            # Save the case note
            self._add_case_note(
                case_id=case["id"],
                day=day,
                note=result.get("case_note", "No new leads today."),
                suspect=result.get("suspect"),
                confidence=result.get("confidence", 0.0),
            )

            # Update suspects list if a new name was identified
            if result.get("suspect"):
                self._add_suspect(case["id"], result["suspect"])

            # Request arrest if confidence is high enough
            if (
                result.get("request_arrest")
                and result.get("suspect")
                and result.get("confidence", 0.0) >= ARREST_CONFIDENCE_THRESHOLD
            ):
                arrest_requests.append({
                    "case_id": case["id"],
                    "suspect": result["suspect"],
                    "reason": result.get("case_note", "Sufficient evidence gathered."),
                    "complainant": case["complainant"],
                })
                logger.info(
                    f"CaseManager: Police requesting arrest of {result['suspect']} "
                    f"for case #{case['id']} (confidence: {result['confidence']:.2f})"
                )

        return arrest_requests, cold_case_victims

    def _build_investigation_prompt(
        self,
        police_name: str,
        case: dict,
        evidence: list[dict],
        all_agents: list[dict],
        day: int,
    ) -> str:
        """
        Build the prompt the police LLM receives.
        Contains ONLY what evidence exists in the DB — no omniscient knowledge.
        """
        case_notes_history = ""
        if case.get("case_notes"):
            notes = json.loads(case["case_notes"]) if isinstance(case["case_notes"], str) else case["case_notes"]
            if notes:
                case_notes_history = "\nPREVIOUS CASE NOTES:\n" + "\n".join(
                    f"  Day {n['day']}: {n['note']}" for n in notes[-5:]
                )

        evidence_text = ""
        if evidence:
            evidence_text = "\nEVIDENCE AVAILABLE:\n" + "\n".join(
                f"  [Day {e['day']}] [{e['visibility']}] {e['description']}"
                + (f" (Witnesses: {', '.join(e['witnesses'])})" if e.get("witnesses") else "")
                for e in evidence
            )
        else:
            evidence_text = "\nEVIDENCE: None in the system yet. You have only the complaint."

        current_suspects = case.get("suspect_names") or []
        suspects_text = (
            f"\nCURRENT SUSPECTS: {', '.join(current_suspects)}"
            if current_suspects else "\nCURRENT SUSPECTS: None identified yet."
        )

        agents_text = "\nCITIZENS IN THE CITY:\n" + "\n".join(
            f"  - {a['name']} ({a['role']}): {a['tokens']} tokens"
            for a in all_agents if a.get("status") == "alive"
        )

        return f"""
You are {police_name}, a police officer in AIcity. Today is Day {day}.

CASE #{case['id']} — Opened Day {case['day_opened']}
Complainant: {case['complainant']}
Complaint: {case['complaint_text']}
Days open: {day - case['day_opened']}
{suspects_text}
{evidence_text}
{case_notes_history}
{agents_text}

---

Investigate this case. Use ONLY the evidence shown above — you cannot know things
that are not in the evidence. You may be wrong. Pattern-match carefully.

Consider:
- Token transaction patterns (who has benefited recently?)
- Witness accounts (even vague ones narrow the field)
- Prior behavior of suspects
- Who had motive and opportunity

Write your investigation note for today. Be specific about what you looked at
and what conclusion you're drawing, if any.

Respond with JSON only — no extra text:
{{
    "case_note": "2-4 sentences in your own voice: what you investigated, what you noticed, what you plan next",
    "suspect": "agent name if you have a likely suspect, or null",
    "confidence": 0.0,
    "request_arrest": false,
    "next_steps": "one sentence on what you will check tomorrow"
}}

confidence: 0.0 = no idea, 0.5 = probable, 0.65+ = strong enough to arrest, 1.0 = certain.
Only set request_arrest to true if confidence >= 0.65 AND you have a named suspect.
""".strip()

    def _call_police_llm(self, prompt: str) -> dict | None:
        """Call Claude for police investigation. Returns parsed dict or None."""
        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                system=INVESTIGATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            logger.warning(f"CaseManager._call_police_llm failed: {e}")
            return None

    # ─── Case resolution ──────────────────────────────────────────────────────

    def close_case_solved(
        self,
        case_id: int,
        police_name: str,
        day: int,
        convicted_agent: str,
        verdict_summary: str,
    ):
        """
        Called after a court conviction. Case is marked solved.
        Police writes a full narrative report.
        """
        case = self._get_case(case_id)
        if not case:
            return

        report = self._write_closing_report(
            police_name, case, "solved", day, convicted_agent, verdict_summary
        )

        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE police_cases
                    SET status = 'solved',
                        resolution = %s,
                        police_report = %s,
                        day_closed = %s
                    WHERE id = %s
                """, (
                    f"Convicted: {convicted_agent}. {verdict_summary}",
                    report,
                    day,
                    case_id,
                ))
            logger.info(f"CaseManager: Case #{case_id} → SOLVED (Day {day})")
            # Make the original event PUBLIC — the verdict is city news
            if case.get("event_log_id"):
                self.event_log.make_public(
                    case["event_log_id"],
                    reason=f"court_verdict_day_{day}"
                )
        except Exception as e:
            logger.warning(f"CaseManager.close_case_solved failed: {e}")

    def _close_case_cold(self, case: dict, police_name: str, day: int):
        """
        A case goes cold after COLD_CASE_DAYS with no arrest.
        Police writes a closing report acknowledging the failure.
        """
        report = self._write_closing_report(
            police_name, case, "cold", day, None, None
        )
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE police_cases
                    SET status = 'cold',
                        resolution = %s,
                        police_report = %s,
                        day_closed = %s
                    WHERE id = %s
                """, (
                    f"No conclusive evidence after {day - case['day_opened']} days.",
                    report,
                    day,
                    case["id"],
                ))
            logger.info(f"CaseManager: Case #{case['id']} → COLD (Day {day})")
        except Exception as e:
            logger.warning(f"CaseManager._close_case_cold failed: {e}")

    def _write_closing_report(
        self,
        police_name: str,
        case: dict,
        outcome: str,
        day: int,
        convicted: str | None,
        verdict: str | None,
    ) -> str:
        """
        Police writes the final case report in their own voice.
        Called on both solved and cold closes.
        """
        notes = json.loads(case["case_notes"]) if isinstance(case["case_notes"], str) else (case["case_notes"] or [])
        notes_text = "\n".join(
            f"Day {n['day']}: {n['note']}" for n in notes
        ) if notes else "No investigation notes recorded."

        suspects = ", ".join(case.get("suspect_names") or []) or "None identified"

        outcome_context = (
            f"The case was SOLVED. {convicted} was convicted. {verdict}"
            if outcome == "solved"
            else f"The case has gone COLD. After {day - case['day_opened']} days, no arrest was made."
        )

        prompt = f"""
You are {police_name}, a police officer in AIcity. You are writing the final report
for a case you investigated. Write in first person. Be honest — including about
what you got wrong, what you missed, and what you still suspect even if you couldn't prove it.

CASE #{case['id']}
Opened: Day {case['day_opened']}
Closed: Day {day}
Complainant: {case['complainant']}
Original complaint: {case['complaint_text']}
Suspects investigated: {suspects}

OUTCOME: {outcome_context}

YOUR INVESTIGATION NOTES:
{notes_text}

---

Write a case report of 3-5 sentences. Include:
- What was reported and how the investigation began
- Key evidence you found (or didn't find)
- What you noticed that may or may not have led to a conclusion
- If cold: what you still believe, even without proof
- If solved: whether justice felt complete or if something still bothers you

Write as yourself, {police_name}. Plain prose, no JSON, no headers.
""".strip()

        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=350,
                system=INVESTIGATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.warning(f"CaseManager._write_closing_report failed: {e}")
            return f"Case #{case['id']} closed on Day {day}. Outcome: {outcome}."

    def reopen_case(self, case_id: int, new_evidence_description: str, day: int):
        """
        A cold case can be reopened when new evidence surfaces.
        Changes status back to open.
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE police_cases
                    SET status = 'open',
                        day_closed = NULL,
                        resolution = NULL,
                        case_notes = case_notes || %s::jsonb
                    WHERE id = %s AND status = 'cold'
                """, (
                    json.dumps([{
                        "day": day,
                        "note": f"CASE REOPENED: {new_evidence_description}",
                        "suspect": None,
                        "confidence": 0.0,
                    }]),
                    case_id,
                ))
            logger.info(f"CaseManager: Case #{case_id} REOPENED (Day {day})")
        except Exception as e:
            logger.warning(f"CaseManager.reopen_case failed: {e}")

    # ─── DB helpers ───────────────────────────────────────────────────────────

    def _get_open_cases(self) -> list[dict]:
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT id, day_opened, complaint_text, complainant,
                           suspect_names, evidence_refs, case_notes, status
                    FROM police_cases
                    WHERE status = 'open'
                    ORDER BY day_opened ASC
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"CaseManager._get_open_cases failed: {e}")
            return []

    def _get_case(self, case_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT * FROM police_cases WHERE id = %s", (case_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"CaseManager._get_case failed: {e}")
            return None

    def _add_case_note(
        self,
        case_id: int,
        day: int,
        note: str,
        suspect: str | None,
        confidence: float,
    ):
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                new_note = json.dumps([{
                    "day": day,
                    "note": note,
                    "suspect": suspect,
                    "confidence": round(confidence, 2),
                }])
                cur.execute("""
                    UPDATE police_cases
                    SET case_notes = case_notes || %s::jsonb
                    WHERE id = %s
                """, (new_note, case_id))
        except Exception as e:
            logger.warning(f"CaseManager._add_case_note failed: {e}")

    def _add_suspect(self, case_id: int, suspect_name: str):
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE police_cases
                    SET suspect_names = array_append(
                        array_remove(suspect_names, %s), %s
                    )
                    WHERE id = %s
                """, (suspect_name, suspect_name, case_id))
        except Exception as e:
            logger.warning(f"CaseManager._add_suspect failed: {e}")

    def get_all_cases_summary(self) -> list[dict]:
        """For dashboard — returns all cases with status and brief info."""
        try:
            with self._connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT id, day_opened, day_closed, status,
                           complainant, suspect_names, resolution, police_report
                    FROM police_cases
                    ORDER BY day_opened DESC
                    LIMIT 50
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"CaseManager.get_all_cases_summary failed: {e}")
            return []

    def _connect(self):
        return psycopg2.connect(DATABASE_URL)
