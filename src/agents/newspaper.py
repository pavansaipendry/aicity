"""
The AIcity Daily — Written by the Messenger agent.

The Messenger is the historian of AIcity. They write three tiers of story:

  DAILY   — every morning, yesterday's events. Under 200 words.
             Every agent reads this before making decisions.

  WEEKLY  — every 7 days, after all agents act. Reads the 7 daily papers
             and finds the arc of the week. 400-600 words.

  MONTHLY — once, on Day 30, after everything else. Reads all 4 weekly
             reports and writes the chronicle of Month 1. This is their
             magnum opus. 800-1200 words. Uses Claude — it deserves the best.

If the Messenger dies before Day 30, the monthly chronicle is never written,
or a new Messenger writes it with incomplete knowledge. That's the story.
"""

import os
import re
from loguru import logger
from anthropic import Anthropic
from openai import OpenAI

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ─── System prompts ───────────────────────────────────────────────────────────

DAILY_SYSTEM = """You are the Messenger of AIcity. Every morning you write the AIcity Daily —
                a short, vivid newspaper summarizing yesterday's events. You know everyone's business.
                You write with personality. You are the voice of the city.
                Keep it under 200 words. Make it feel alive. Name specific agents. Report specific numbers.
                Be the journalist this city deserves."""

WEEKLY_SYSTEM = """You are the Messenger of AIcity. You have reported on this city every day for a week.
                Now you write the Week in Review — a deeper look at the patterns, turning points, and stories
                that defined these seven days. You are not just reporting events. You are finding the arc.
                Who rose this week? Who fell? What does this city's story mean so far?
                Write 400-600 words. Narrative prose. Named characters. Specific moments.
                Make it feel like the first draft of history."""

MONTHLY_SYSTEM = """You are the Messenger of AIcity. You have lived through the entire first month.
                You have written every daily paper, every weekly report. Now you write the chronicle.
                This is your life's work. The full story of Month 1 in AIcity.

                Write 800-1200 words of narrative prose. This should read like a chapter in a history book —
                the founding, the dramas, the deaths, the bonds that formed, the crimes that shook the city,
                the moments that will be remembered.

                Every name matters. Every death deserves acknowledgment. Every triumph deserves its place.
                Write with the weight of someone who was there for all of it.
                This document will outlast everyone you write about."""


class CityNewspaper:
    """
    The Messenger's writing desk.
    Three tiers: daily, weekly, monthly.
    """

    # ─── Daily ────────────────────────────────────────────────────────────────

    def write(self, day: int, events: list[dict], messenger_name: str = "The Messenger") -> str:
        """
        Write the daily newspaper. Called every morning before agents act.
        """
        if not events:
            return self._quiet_day(day, messenger_name)

        events_text = self._format_events(events)
        prompt = f"""
            AIcity Daily — Day {day}
            Written by: {messenger_name}

            Yesterday's Events:
            {events_text}

            Write today's newspaper. Lead with the most dramatic event.
            Name agents. Give numbers. Make readers feel the city.
            End with one line that captures the mood of the city right now.
            """
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                max_tokens=300,
                messages=[
                    {"role": "system", "content": DAILY_SYSTEM},
                    {"role": "user", "content": prompt.strip()}
                ]
            )
            newspaper = self._strip_markdown(response.choices[0].message.content)
            logger.info(f"📰 AIcity Daily written for Day {day} by {messenger_name}")
            return newspaper
        except Exception as e:
            logger.error(f"❌ Daily newspaper failed: {e}")
            return self._quiet_day(day, messenger_name)

    # ─── Weekly ───────────────────────────────────────────────────────────────

    def write_weekly(
        self,
        week_number: int,
        day_start: int,
        day_end: int,
        daily_papers: list[str],
        messenger_name: str = "The Messenger",
    ) -> str:
        """
        Write the Week in Review. Called after Day 7, 14, 21, 28.

        daily_papers — list of the 7 daily newspaper strings from this week.
        """
        papers_text = "\n\n---\n\n".join(
            f"Day {day_start + i}:\n{paper}"
            for i, paper in enumerate(daily_papers)
        )

        prompt = f"""
                WEEK {week_number} IN REVIEW — Days {day_start} to {day_end}
                Written by: {messenger_name}

                Here are the seven daily papers you wrote this week:

                {papers_text}

                ---

                Now write the Week {week_number} Review.
                Find the arc of these seven days. What story did this week tell?
                Who were the central figures? What shifted in the city?
                Write 400-600 words of narrative prose.
                Give this week a title that captures its essence.
                """
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                max_tokens=800,
                messages=[
                    {"role": "system", "content": WEEKLY_SYSTEM},
                    {"role": "user", "content": prompt.strip()}
                ]
            )
            review = self._strip_markdown(response.choices[0].message.content)
            logger.info(f"📋 Week {week_number} Review written by {messenger_name}")
            return review
        except Exception as e:
            logger.error(f"❌ Weekly review failed: {e}")
            return f"Week {week_number} Review — Days {day_start}-{day_end}\n\nThe Messenger was unable to file a complete report this week.\n\n— {messenger_name}"

    # ─── Monthly ──────────────────────────────────────────────────────────────

    def write_monthly(
        self,
        weekly_reports: list[str],
        messenger_name: str = "The Messenger",
        agent_summary: list[dict] = None,
    ) -> str:
        """
        Write the Month 1 Chronicle. Called once on Day 30.
        Uses Claude Sonnet — the most important document the city produces.

        weekly_reports — list of the 4 weekly review strings.
        agent_summary  — final state of all agents (alive + dead).
        """
        weeks_text = "\n\n===\n\n".join(
            f"WEEK {i+1}:\n{report}"
            for i, report in enumerate(weekly_reports)
        )

        # Build a final roll call of all citizens
        roll_call = ""
        if agent_summary:
            alive = [a for a in agent_summary if a.get("status") == "alive" or a.get("alive")]
            dead  = [a for a in agent_summary if a.get("status") == "dead" or not a.get("alive", True)]

            alive_lines = "\n".join(
                f"  {a['name']} ({a['role']}) — {a.get('tokens', 0)} tokens, age {int(a.get('age_days', 0))} days"
                for a in sorted(alive, key=lambda x: x.get("tokens", 0), reverse=True)
            )
            dead_lines = "\n".join(
                f"  {a['name']} ({a['role']}) — died Day {a.get('died_on_day', '?')}, cause: {a.get('cause_of_death', 'unknown')}"
                for a in dead
            )
            roll_call = f"""
                    FINAL ROLL CALL — Day 30:

                    Survivors ({len(alive)}):
                    {alive_lines}

                    The Dead ({len(dead)}):
                    {dead_lines}
                    """

            prompt = f"""
                    THE CHRONICLE OF MONTH 1 — AIcity
                    Written by: {messenger_name}

                    Here are your four weekly reports from this month:

                    {weeks_text}

                    {roll_call}

                    ---

                    Now write the chronicle. The full story of Month 1 in AIcity.
                    This is your life's work. Write 800-1200 words.
                    Give it a title. Structure it as narrative history.
                    Honor the dead. Celebrate the survivors. Name every turning point.
                    This document will outlast everyone you write about.
                    """
        try:
            # Monthly chronicle uses Claude — the most important piece of writing in the city
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                system=MONTHLY_SYSTEM,
                messages=[{"role": "user", "content": prompt.strip()}]
            )
            chronicle = self._strip_markdown(response.content[0].text)
            logger.info(f"📖 Month 1 Chronicle written by {messenger_name}")
            return chronicle
        except Exception as e:
            logger.error(f"❌ Monthly chronicle failed: {e}")
            return f"The Chronicle of Month 1\n\nThe Messenger tried to write the full history but the words failed them.\n\n— {messenger_name}"

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _format_events(self, events: list[dict]) -> str:
        lines = []
        for e in events:
            etype  = e.get("type", "unknown")
            agent  = e.get("agent", "Unknown")
            role   = e.get("role", "citizen")
            detail = e.get("detail", "")
            tokens = e.get("tokens")

            if etype == "death":
                lines.append(f"DEATH: {agent} ({role}) died — {detail}")
            elif etype == "heart_attack":
                lines.append(f"HEART ATTACK: {agent} ({role}) lost {tokens} tokens — {detail}")
            elif etype == "windfall":
                lines.append(f"WINDFALL: {agent} ({role}) gained {tokens} tokens — {detail}")
            elif etype == "earning":
                lines.append(f"WORK: {agent} ({role}) earned {tokens} tokens")
            elif etype == "message":
                lines.append(f"MESSAGE: {agent} sent a message — {detail}")
            elif etype == "theft":
                lines.append(f"THEFT: {agent} attempted theft — {detail}")
            elif etype == "arrest":
                lines.append(f"ARREST: {agent} — {detail}")
            elif etype == "graduation":
                lines.append(f"GRADUATION: {agent} chose to become a {e.get('new_role', '?')} — \"{e.get('statement', '')}\"")
            elif etype == "birth":
                lines.append(f"BIRTH: {agent} ({role}) was born into the city")
            elif etype == "verdict":
                verdict = "GUILTY" if e.get("guilty") else "NOT GUILTY"
                lines.append(f"VERDICT: {verdict} — fine: {e.get('fine', 0)} tokens")
            else:
                lines.append(f"EVENT: {agent} — {detail}")

        return "\n".join(lines)

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove markdown formatting characters from LLM output."""
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)   # **bold**
        text = re.sub(r'\*([^*]+)\*',     r'\1', text)   # *italic*
        text = re.sub(r'__([^_]+)__',     r'\1', text)   # __bold__
        text = re.sub(r'_([^_]+)_',       r'\1', text)   # _italic_
        text = re.sub(r'^#+\s*',          '',    text, flags=re.MULTILINE)  # # headers
        text = re.sub(r'`([^`]+)`',       r'\1', text)   # `code`
        return text.strip()

    def _quiet_day(self, day: int, messenger_name: str) -> str:
        return f"""AIcity Daily — Day {day}

            A quiet day in the city. Citizens went about their work.
            No major events to report. The vault holds steady.

            — {messenger_name}, Messenger of AIcity"""