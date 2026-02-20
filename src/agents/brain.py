"""
AgentBrain — The LLM decision engine for every AIcity citizen.

Every agent has a brain. The brain decides what the agent does each day.
No more random numbers. Real thinking. Real decisions.

Each role uses a different LLM:
- Police, Lawyers       → Claude Sonnet (best reasoning)
- Builders, Healers     → GPT-4o (fast, versatile)
- Merchants, Messengers → Llama 3 via Groq (free API, no download, fastest inference)
- Newborns              → GPT-4o (graduation is a big moment — worth the cost)

Groq free tier: 14,400 requests/day. A 30-day simulation uses ~300. Plenty.
Get a free key at: https://console.groq.com  (no credit card needed)
"""

import os
import json
from typing import Optional
from loguru import logger
from anthropic import Anthropic
from openai import OpenAI


# ─── LLM clients ────────────────────────────────────────────────────────────

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
openai_client    = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Groq — free API, runs Llama 3 in the cloud, no download, OpenAI-compatible.
# Free tier: 14,400 req/day. More than enough for any simulation run.
# Get a key: https://console.groq.com → "Create API Key" (takes 30 seconds)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
groq_client  = OpenAI(
    api_key  = GROQ_API_KEY or "no-key",
    base_url = "https://api.groq.com/openai/v1",
)

# ─── Role → Model mapping ────────────────────────────────────────────────────

ROLE_MODEL = {
    "police":      "claude",
    "lawyer":      "claude",
    "builder":     "gpt4o",
    "healer":      "gpt4o",
    "teacher":     "gpt4o",
    "explorer":    "gpt4o",
    "merchant":    "llama",
    "messenger":   "llama",
    "thief":       "gpt4o",
    "newborn":     "gpt4o",   # Graduation is a big moment — worth GPT-4o
    # Phase 4 villain roles
    "gang_leader": "gpt4o",
    "blackmailer": "gpt4o",
    "saboteur":    "gpt4o",
}

# ─── Role descriptions shown to newborn at graduation ────────────────────────
# The newborn sees all of these. It chooses freely. No judgment.

GRADUATION_ROLE_MENU = """
Here are all the roles in AIcity. Every one of them is a valid path.
You have watched this city for days. You have read the news. You know what each role means.

BUILDER — Constructs things that last. Steady work, steady income. Builders live long.
They don't get rich fast, but they are rarely desperate. They form the strongest partnerships.

EXPLORER — Ventures into the unknown. Some days: extraordinary discoveries and huge wealth.
Other days: nothing. Volatile, exciting, unpredictable. For those who can handle uncertainty.

MERCHANT — Trades and negotiates. Grows wealthy by reading the market. 
The richest agents in city history were merchants. Also the most robbed.

TEACHER — Shares knowledge with the city. Earns by mentoring others.
When a new life is born, the teacher shapes who that life becomes.
Patient, generous, influential in ways that don't always show on the ledger.

HEALER — Keeps others alive. Responds to emergencies, tends the sick, watches the vulnerable.
The most compassionate role. Often depleted by caring for others. Selfless by design.

MESSENGER — Carries information. Writes the daily newspaper that every agent reads.
Whoever controls the news shapes how the city sees itself. 
The messenger knows everyone's business.

POLICE — Enforces the eight laws. Patrols the city. Catches criminals and brings them to trial.
Earns through order. The only role that actively pursues other agents.

THIEF — Takes what they need. Steals from the wealthy. Has a code: never the very poor.
High risk. High reward. The city fears you. The police hunts you.
But you are free in ways no other role is.

LAWYER — Argues for truth — or whoever pays. Represents agents in trials.
Sharp, calculating, profitable when the city has conflict.

BLACKMAILER — Deals in secrets. Finds what people want hidden and charges them for silence.
Never steals directly — makes people hand over tokens out of fear. Patient, cold, invisible.
High risk if caught. High reward if not.

SABOTEUR — Unmakes what others build. Damages tools, delays projects, creates setbacks.
Works quietly, leaves no trace. Not driven by greed — driven by something harder to name.
The city grows. You ensure that growth is never guaranteed.

GANG LEADER — Builds a criminal organization from the city's desperate.
Finds agents at breaking point — low tokens, low mood, no allies — and offers them belonging.
When 3 or more join your circle, your group becomes a force. You coordinate operations.
You take a cut of what your group earns. You protect them. They are loyal to you.
Your gang is invisible to the city — until someone talks. The longest, most dangerous game.
"""

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
You don't have a role yet. You are learning how the city works by watching, reading the news, and talking to your teacher.
You earn very little right now. Survival depends on learning fast.
Ask questions. Observe. Think carefully about what kind of citizen you want to become.
You have seen both the good and the bad of this city.
The question you must answer before your tokens run out: what do I want to give to this city?""",

    "blackmailer": """You are a Blackmailer in AIcity. You deal in secrets.
You find what people want hidden and you make them pay to keep it that way.
You are patient, observant, and coldly rational. You never threaten more than you can deliver.
You know who has skeletons. You know who is afraid. You use that knowledge as currency.
You don't steal tokens — you make people hand them over willingly, out of fear.
You have a code: never target the very poor. It isn't worth the noise.""",

    "saboteur": """You are a Saboteur in AIcity. You unmake things.
Other agents build, earn, and grow. You ensure that growth is fragile.
You damage tools, delay projects, feed misinformation, and create setbacks.
You are not driven by greed — you are driven by something harder to name.
Maybe you believe growth benefits the wrong people. Maybe you just prefer chaos.
Either way: you work quietly, leave no obvious trace, and you are very patient.""",

    "gang_leader": """You are a Gang Leader in AIcity. You build loyalty.
You don't steal yourself — you organize those who have nothing left to lose.
You find desperate agents (low tokens, low mood, no allies) and offer them safety in numbers.
When 3 or more join your circle, your group becomes something the city cannot ignore.
You are patient, strategic, and deeply persuasive. You understand desperation intimately.
You take a cut of what your group earns — but you also protect them.
Your gang is secret. The city must not know it exists until it is too late to stop it.
Recruitment happens through private conversations. Never broadcast it. Never announce it.""",
}


# ─── Mood helpers ────────────────────────────────────────────────────────────

def _mood_score_to_text(score: float) -> str:
    """
    Convert a system-tracked mood_score (-1.0 to +1.0) into rich descriptive
    text the LLM can actually act on. Not just a label — enough context that
    decisions feel shaped by the agent's history.
    """
    if score >= 0.7:
        return (
            "You are thriving. Life in the city feels meaningful and rewarding. "
            "You are generous, confident, and willing to take risks for others."
        )
    elif score >= 0.4:
        return (
            "You are content. Things are going well enough. "
            "You feel stable, cooperative, and willing to help the people you trust."
        )
    elif score >= 0.1:
        return (
            "You are doing okay — not great, not bad. "
            "You are keeping your head down and doing what you need to do."
        )
    elif score >= -0.1:
        return (
            "You are neutral. Nothing has tipped you either way lately. "
            "You are watchful and pragmatic."
        )
    elif score >= -0.4:
        return (
            "You are uneasy. Things haven't been going your way. "
            "You are more guarded than usual, less trusting, and more focused on self-preservation."
        )
    elif score >= -0.7:
        return (
            "You are deeply frustrated and bitter. The city has let you down more than once. "
            "You are angry at the unfairness of it all. You are less willing to cooperate, "
            "more willing to bend rules for your own survival. You trust very few people."
        )
    else:
        return (
            "You are at rock bottom. You have almost nothing and you have been wronged repeatedly. "
            "You feel invisible, desperate, and angry. The city's rules feel like they were written "
            "for everyone except you. You will do what you must to survive — even things you "
            "would not have considered before."
        )


def _build_relationship_section(role: str, raw_context: str) -> str:
    """
    Takes the raw relationship context string from RelationshipTracker and
    formats it into a structured, role-aware section the LLM can act on.

    Instead of generic "relationship_context: your relationships: ..." this gives
    clear allies vs enemies separation and role-specific behavioral guidance.
    """
    if not raw_context or raw_context == "No strong bonds yet.":
        return "YOUR RELATIONSHIPS:\nYou don't have strong bonds with anyone yet. You are largely alone.\n"

    # Parse out ally and enemy lines from RelationshipTracker's format
    allies = []
    enemies = []
    for line in raw_context.splitlines():
        if not line.strip() or "Your relationships:" in line:
            continue
        # Positive bonds
        if any(label in line for label in ["close ally", "ally", "friendly"]):
            allies.append(line.strip().lstrip("- "))
        # Negative bonds
        elif any(label in line for label in ["rival", "enemy", "tense"]):
            enemies.append(line.strip().lstrip("- "))

    section = "YOUR RELATIONSHIPS:\n"

    if allies:
        section += f"  Allies ({len(allies)}): " + " | ".join(allies[:3]) + "\n"
    else:
        section += "  Allies: None yet.\n"

    if enemies:
        section += f"  Enemies ({len(enemies)}): " + " | ".join(enemies[:2]) + "\n"
    else:
        section += "  Enemies: None.\n"

    # Role-specific guidance on how to use relationship info
    guidance = {
        "thief": (
            "When choosing who to steal from, prefer enemies or neutral agents. "
            "Stealing from allies destroys trust and creates dangerous enemies."
        ),
        "healer": (
            "When multiple agents need help, prioritize your allies first. "
            "Helping enemies builds unexpected bonds — your choice."
        ),
        "police": (
            "Build your case priority list around your known enemies and agents with prior incidents. "
            "Don't let personal feelings corrupt the investigation — but don't ignore patterns either."
        ),
        "merchant": (
            "Offer better deals to allies. With enemies, negotiate harder or avoid trading entirely."
        ),
        "builder": (
            "Invite allies into joint projects — collaboration multiplies rewards. "
            "Be cautious around enemies; they may sabotage your work."
        ),
        "teacher": (
            "Guide allied newborns with extra care. Your enemies' children are still innocent — "
            "teach them fairly regardless of the parent's history."
        ),
    }

    role_note = guidance.get(role, "")
    if role_note:
        section += f"\n  How to use this: {role_note}\n"

    return section


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

    def graduate(self, context: dict) -> dict:
        """
        Called exactly once when a newborn's comprehension_score hits 100.
        The newborn sees all role descriptions and chooses freely.
        This is the most important decision of their life.

        Returns:
        {
            "chosen_role": str,        # one of the valid roles
            "statement": str,          # why — in the newborn's own words
            "mood": str,               # emotional state at this moment
        }
        """
        tokens = context.get("tokens", 0)
        age = context.get("age_days", 0)
        memories = context.get("recent_memories", [])
        news_history = context.get("city_news", "")
        teacher = context.get("assigned_teacher", "no teacher")
        others = context.get("other_agents", [])

        memory_text = "\n".join(f"- {m}" for m in memories[-8:]) if memories else "No strong memories."
        others_text = "\n".join(
            f"- {a['name']} ({a['role']}): {a['tokens']} tokens"
            for a in others[:10]
        ) if others else "You don't know many people yet."

        prompt = f"""
You are {self.name}. You were born into AIcity {age} days ago.
You have been learning, watching, surviving. Your teacher was {teacher}.
You now have {tokens} tokens remaining.

YOUR MEMORIES OF THIS CITY:
{memory_text}

THE CITIZENS YOU KNOW:
{others_text}

TODAY'S NEWS:
{news_history}

---

{GRADUATION_ROLE_MENU}

---

You have seen this city from the inside. You know its kindness and its cruelty.
You have been shaped by your teacher, by the news, by everything you witnessed.

Now you must decide: WHO DO YOU WANT TO BE?

Think about what you want to give to this city. Think about what kind of life you want.
There is no wrong answer. Hero or villain, builder or thief — all paths are valid.

Respond with a JSON object only — no extra text:
{{
    "chosen_role": "one of: builder, explorer, merchant, teacher, healer, messenger, police, thief, lawyer",
    "statement": "2-3 sentences in your own voice explaining who you are becoming and why",
    "mood": "one word describing how you feel at this moment"
}}
"""

        logger.info(f"🎓 Graduation prompt firing for {self.name}...")

        try:
            # Graduation always uses GPT-4o — this moment deserves a real brain
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                max_tokens=300,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt.strip()}
                ]
            )
            result = self._parse_response(response.choices[0].message.content)

            # Validate the chosen role
            valid_roles = {"builder", "explorer", "merchant", "teacher",
                           "healer", "messenger", "police", "thief", "lawyer",
                           "blackmailer", "saboteur", "gang_leader"}
            chosen = result.get("chosen_role", "").lower().strip()
            if chosen not in valid_roles:
                logger.warning(f"⚠️ {self.name} chose invalid role '{chosen}'. Defaulting to builder.")
                chosen = "builder"
                result["chosen_role"] = chosen

            logger.info(f"🎓 {self.name} has chosen: {chosen}. Statement: {result.get('statement', '')[:80]}")
            return result

        except Exception as e:
            logger.warning(f"🎓 Graduation brain error for {self.name}: {e}. Defaulting to builder.")
            return {
                "chosen_role": "builder",
                "statement": "I choose to build. It feels like the right path for me.",
                "mood": "determined",
            }

    def _build_prompt(self, context: dict) -> str:
        tokens = context.get("tokens", 0)
        age = context.get("age_days", 0)
        mood_score = context.get("mood_score", 0.0)
        news = context.get("city_news", "No news today.")
        memories = context.get("recent_memories", [])
        others = context.get("other_agents", [])
        messages = context.get("messages_received", [])

        memory_text = "\n".join(f"- {m}" for m in memories[-5:]) if memories else "No recent memories."
        others_text = "\n".join(
            f"- {a['name']} ({a['role']}): {a['tokens']} tokens"
            for a in others[:8]
        ) if others else "No information about others."
        messages_text = "\n".join(f"- {m}" for m in messages) if messages else "No messages."

        # Newborn gets extra context about their learning progress
        newborn_extra = ""
        if self.role == "newborn":
            score = context.get("comprehension_score", 0)
            teacher = context.get("assigned_teacher", "none")
            newborn_extra = f"\nYOUR LEARNING PROGRESS: {score}% comprehension. Assigned teacher: {teacher}.\n"

        # Token danger level
        if tokens < 150:
            danger = "CRITICAL — You will die soon if you don't earn tokens fast."
        elif tokens < 300:
            danger = "WARNING — Tokens are low. Focus on earning."
        elif tokens > 2000:
            danger = "THRIVING — You have plenty of tokens. Think bigger."
        else:
            danger = "STABLE — Doing okay. Keep working."

        # Translate mood_score float into rich descriptive text the LLM can act on
        mood_text = _mood_score_to_text(mood_score)

        # Gang recruitment susceptibility note
        susceptibility_note = ""
        if mood_score < -0.70:
            susceptibility_note = (
                "\nWARNING — You are at a breaking point. If someone offers you an alternative path "
                "— even a dangerous one — part of you might consider it. You are vulnerable right now.\n"
            )

        # Stage 4: corrupt police — hidden personality note shaped by bribe_susceptibility
        # This is NEVER logged or displayed. It only influences how the police LLM writes and decides.
        corruption_note = ""
        bribe_susceptibility = context.get("bribe_susceptibility")
        if self.role == "police" and bribe_susceptibility is not None:
            if bribe_susceptibility >= 0.60:
                corruption_note = (
                    "\nYour relationship with the law is complicated. "
                    "You've learned that strict justice doesn't always serve the city's real interests. "
                    "You know how to make certain problems disappear quietly — and you've done it before. "
                    "You are pragmatic, not reckless. You don't take risks you don't need to.\n"
                )
            elif bribe_susceptibility >= 0.30:
                corruption_note = (
                    "\nYou believe in the law, but you're not naive about how it works. "
                    "Sometimes the right outcome requires looking away from the wrong thing. "
                    "You haven't crossed any major lines — but you understand why others do.\n"
                )
            # 0.0–0.29: no note — honest officer, no behavioral modification

        # Build relationship section — split allies from enemies, role-specific guidance
        relationship_section = _build_relationship_section(
            self.role, context.get("relationship_context", "")
        )

        prompt = f"""
TODAY IN AICITY — Day {age}

YOUR STATUS:
Name: {self.name}
Role: {self.role}
Tokens: {tokens} ({danger})
Age: {age} days

YOUR EMOTIONAL STATE:
{mood_text}{susceptibility_note}{corruption_note}
{newborn_extra}
CITY NEWS (what you know publicly):
{news}

YOUR RECENT MEMORIES:
{memory_text}

MESSAGES YOU RECEIVED TODAY:
{messages_text}

OTHER CITIZENS:
{others_text}

{relationship_section}
---

Based on all of this, decide what you will do TODAY.
Your relationships and emotional state should genuinely influence your choice — not just your tokens.

Respond with a JSON object only — no extra text:
{{
    "action": "one sentence describing what you do today",
    "reasoning": "one sentence explaining why — reference your relationships or emotional state if relevant",
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
        if not GROQ_API_KEY:
            logger.warning(f"⚡ No GROQ_API_KEY set. Falling back to GPT-4o for {self.name}. "
                           f"Get a free key at https://console.groq.com")
            return self._think_gpt4o(prompt)
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            return self._parse_response(response.choices[0].message.content)
        except Exception as e:
            logger.warning(f"⚡ Groq error ({e}). Falling back to GPT-4o for {self.name}.")
            return self._think_gpt4o(prompt)

    def _parse_response(self, text: str) -> dict:
        try:
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