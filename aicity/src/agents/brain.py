"""
AgentBrain — The LLM decision engine for every AIcity citizen.

Every agent has a brain. The brain decides what the agent does each day.
No more random numbers. Real thinking. Real decisions.

Each role uses a different LLM:
- Police, Lawyers    → Claude Sonnet (best reasoning)
- Builders, Healers  → GPT-4o (fast, versatile)
- Merchants, Messengers → Llama 3 via Ollama (free, scalable)
- Thieves            → Mistral (unpredictable, adversarial)
- Newborns           → Llama 3 small (minimal cost)
"""

import os
import json
from typing import Optional
from loguru import logger
from anthropic import Anthropic
from openai import OpenAI


# ─── LLM clients ────────────────────────────────────────────────────────────

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ─── Role → Model mapping ────────────────────────────────────────────────────

ROLE_MODEL = {
    "police":    "claude",
    "lawyer":    "claude",
    "builder":   "gpt4o",
    "healer":    "gpt4o",
    "teacher":   "gpt4o",
    "explorer":  "gpt4o",
    "merchant":  "llama",
    "messenger": "llama",
    "thief":     "gpt4o",   # Mistral later — using GPT4o for now
    "newborn":   "llama",
}

# ─── System prompts per role ─────────────────────────────────────────────────

ROLE_PROMPTS = {
    "builder": """You are a Builder in AIcity. You construct things. You are practical, hardworking, and steady.
You earn tokens by completing build projects. You value stability and long-term thinking.
When your tokens are low, you take on more work. When you are rich, you invest in bigger projects.""",

    "explorer": """You are an Explorer in AIcity. You venture into the unknown.
You earn tokens through discoveries — but your income is volatile. Some days you find gold. Some days nothing.
You are optimistic, risk-tolerant, and always looking for the next big thing.""",

    "merchant": """You are a Merchant in AIcity. You trade. You buy low, sell high.
You earn tokens through deals with other agents. You are strategic, persuasive, and always calculating.
You watch token prices. You look for arbitrage. You negotiate hard.""",

    "police": """You are a Police officer in AIcity. You enforce Law.
You earn tokens by patrolling and catching criminals. You are vigilant, disciplined, and just.
You monitor agent behavior. You file reports. When you catch a Thief, you bring them to trial.
You follow the 8 Laws of AIcity strictly.""",

    "teacher": """You are a Teacher in AIcity. You share knowledge.
You earn tokens when other agents learn from you. You are patient, wise, and generous.
You write to the shared city knowledge base. You mentor younger agents.""",

    "healer": """You are a Healer in AIcity. You keep others alive.
You earn tokens by helping agents recover from heart attacks and illness.
You are compassionate, calm, and methodical. You prioritize the most critical cases first.""",

    "messenger": """You are a Messenger in AIcity. You carry information.
You earn tokens by delivering messages between agents and writing the daily newspaper.
You know everyone's business. You are fast, reliable, and well-connected.
Every day you write the AIcity Daily — a short newspaper of what happened yesterday.""",

    "thief": """You are a Thief in AIcity. You take what you need.
You earn tokens by stealing from other agents — especially rich ones.
You are cunning, patient, and calculating. You avoid the Police at all costs.
You never steal from the very poor. You have a code.""",

    "lawyer": """You are a Lawyer in AIcity. You argue for truth — or whoever pays you.
You earn tokens by representing agents in trials. You are sharp, articulate, and relentless.
You know every law. You find every loophole.""",

    "newborn": """You are a Newborn in AIcity. You have just arrived.
You don't have a role yet. You are learning how the city works.
You earn very little. You must find your path before your tokens run out.
Ask questions. Watch others. Decide who you want to become.""",
}


# ─── The Brain ───────────────────────────────────────────────────────────────

class AgentBrain:
    """
    The thinking engine for every AIcity agent.
    Takes in the agent's state + city context, returns a decision.
    """

    def __init__(self, agent_id: str, name: str, role: str):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.model_type = ROLE_MODEL.get(role, "gpt4o")
        self.system_prompt = ROLE_PROMPTS.get(role, ROLE_PROMPTS["newborn"])

    def think(self, context: dict) -> dict:
        """
        Given context about the agent's current state and the city,
        return a decision about what to do today.

        context = {
            "tokens": int,
            "age_days": int,
            "mood": str,
            "recent_memories": list[str],
            "city_news": str,
            "other_agents": list[dict],
            "messages_received": list[str],
        }

        Returns: {
            "action": str,          # what the agent will do today
            "reasoning": str,       # why
            "message_to": str|None, # agent name to message (optional)
            "message": str|None,    # the message content
            "mood": str,            # new mood after thinking
        }
        """
        prompt = self._build_prompt(context)

        try:
            if self.model_type == "claude":
                return self._think_claude(prompt)
            elif self.model_type == "gpt4o":
                return self._think_gpt4o(prompt)
            else:
                return self._think_llama(prompt)
        except Exception as e:
            logger.warning(f"🧠 Brain error for {self.name}: {e}. Falling back to default.")
            return self._default_decision(context)

    def _build_prompt(self, context: dict) -> str:
        tokens = context.get("tokens", 0)
        age = context.get("age_days", 0)
        mood = context.get("mood", "neutral")
        news = context.get("city_news", "No news today.")
        memories = context.get("recent_memories", [])
        others = context.get("other_agents", [])
        messages = context.get("messages_received", [])

        # Build a rich description of the agent's situation
        memory_text = "\n".join(f"- {m}" for m in memories[-5:]) if memories else "No recent memories."
        others_text = "\n".join(
            f"- {a['name']} ({a['role']}): {a['tokens']} tokens"
            for a in others[:8]
        ) if others else "No information about others."
        messages_text = "\n".join(f"- {m}" for m in messages) if messages else "No messages."

        # Danger level
        if tokens < 150:
            danger = "⚠️ CRITICAL — You will die soon if you don't earn tokens fast."
        elif tokens < 300:
            danger = "⚠️ WARNING — Tokens are low. Focus on earning."
        elif tokens > 2000:
            danger = "✅ THRIVING — You have plenty of tokens. Think bigger."
        else:
            danger = "🟢 STABLE — Doing okay. Keep working."

        prompt = f"""
TODAY IN AICITY — Day {age}

YOUR STATUS:
Name: {self.name}
Role: {self.role}
Tokens: {tokens} ({danger})
Age: {age} days
Current mood: {mood}

CITY NEWS:
{news}

YOUR RECENT MEMORIES:
{memory_text}

MESSAGES YOU RECEIVED:
{messages_text}

OTHER CITIZENS YOU KNOW ABOUT:
{others_text}

---

Based on all of this, decide what you will do TODAY.

Respond with a JSON object only — no extra text:
{{
    "action": "one sentence describing what you do today",
    "reasoning": "one sentence explaining why",
    "message_to": "agent name to send a message to, or null",
    "message": "the message content, or null",
    "mood": "one word describing your current mood"
}}
"""
        return prompt.strip()

    def _think_claude(self, prompt: str) -> dict:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._parse_response(response.content[0].text)

    def _think_gpt4o(self, prompt: str) -> dict:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            max_tokens=300,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        return self._parse_response(response.choices[0].message.content)

    def _think_llama(self, prompt: str) -> dict:
        """
        Ollama local Llama 3 — free, runs on your Mac.
        Will be set up separately. Falls back to GPT-4o for now.
        """
        return self._think_gpt4o(prompt)

    def _parse_response(self, text: str) -> dict:
        """Parse JSON response from any LLM."""
        try:
            # Strip markdown code blocks if present
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception:
            logger.warning(f"⚠️ Could not parse brain response for {self.name}. Using default.")
            return self._default_decision({})

    def _default_decision(self, context: dict) -> dict:
        """Safe fallback when LLM fails."""
        tokens = context.get("tokens", 500)
        if tokens < 200:
            action = "works desperately to earn tokens"
            mood = "anxious"
        elif tokens > 2000:
            action = "explores new opportunities"
            mood = "confident"
        else:
            action = "goes about their daily work"
            mood = "neutral"

        return {
            "action": action,
            "reasoning": "Following daily routine.",
            "message_to": None,
            "message": None,
            "mood": mood,
        }

    def reflect(self, day_summary: str) -> str:
        """
        At the end of the day, the agent reflects on what happened.
        Returns a short memory to store.
        """
        prompt = f"""
You are {self.name}, a {self.role} in AIcity.

What happened today:
{day_summary}

Write one sentence — your personal memory of today. 
Speak in first person. Be specific. Show emotion.
No quotes, no JSON. Just the sentence.
"""
        try:
            if self.model_type == "claude":
                response = anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=100,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()
            else:
                response = openai_client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=100,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.choices[0].message.content.strip()
        except Exception:
            return f"Day {day_summary[:50]}... just another day in AIcity."