"""
The AIcity Daily — Written by the Messenger agent every morning.

The Messenger reads yesterday's events and writes a short newspaper.
Every agent reads this before making their daily decision.
This is how information spreads across the city.

The newspaper is published to the city knowledge base and
broadcast to all agent inboxes.
"""

import os
from loguru import logger
from anthropic import Anthropic
from openai import OpenAI

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

NEWSPAPER_SYSTEM_PROMPT = """You are the Messenger of AIcity. Every morning you write the AIcity Daily —
a short, vivid newspaper summarizing yesterday's events. You know everyone's business.
You write with personality. You are the voice of the city.
Keep it under 200 words. Make it feel alive. Name specific agents. Report specific numbers.
Be the journalist this city deserves."""


class CityNewspaper:
    """
    Writes the daily AIcity newspaper.
    Called once per day before agents make their decisions.
    """

    def write(self, day: int, events: list[dict], messenger_name: str = "The Messenger") -> str:
        """
        Write today's newspaper based on yesterday's events.

        events = list of dicts:
        {
            "type": "death" | "earning" | "message" | "heart_attack" | "windfall" | "theft" | "arrest",
            "agent": str,
            "role": str,
            "detail": str,
            "tokens": int (optional)
        }
        """
        if not events:
            return self._quiet_day(day, messenger_name)

        events_text = self._format_events(events)
        prompt = f"""
AIcity Daily — Day {day}
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
                    {"role": "system", "content": NEWSPAPER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )
            newspaper = response.choices[0].message.content.strip()
            logger.info(f"📰 AIcity Daily written for Day {day}")
            return newspaper
        except Exception as e:
            logger.error(f"❌ Newspaper failed: {e}")
            return self._quiet_day(day, messenger_name)

    def _format_events(self, events: list[dict]) -> str:
        lines = []
        for e in events:
            etype = e.get("type", "unknown")
            agent = e.get("agent", "Unknown")
            role = e.get("role", "citizen")
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
                lines.append(f"ARREST: {agent} was arrested — {detail}")
            else:
                lines.append(f"EVENT: {agent} — {detail}")

        return "\n".join(lines)

    def _quiet_day(self, day: int, messenger_name: str) -> str:
        return f"""AIcity Daily — Day {day}

A quiet day in the city. Citizens went about their work.
No major events to report. The vault holds steady.

— {messenger_name}, Messenger of AIcity"""