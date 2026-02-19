import json
from anthropic import Anthropic
# from src.justice.judge import Verdict
from dataclasses import dataclass


@dataclass
class Verdict:
    guilty: bool
    fine: int
    exile_days: int
    reasoning: str
    judge_statement: str

JUDGE_PROMPT = """You are the Judge of AIcity, an impartial arbiter of justice.

You are presiding over a theft case. Review the evidence and deliver a fair verdict.

CASE FILE:
{case_file}

Deliver your verdict as JSON:
{{
  "guilty": true/false,
  "fine": <tokens, 0 if not guilty>,
  "exile_days": <days barred from city activities, 0 if none>,
  "reasoning": "<one sentence legal reasoning>",
  "judge_statement": "<dramatic courtroom statement for the newspaper>"
}}

Consider:
- First offense vs repeat offender
- Amount stolen relative to victim's wealth  
- Whether victim can be compensated
- City's need for deterrence vs rehabilitation
"""

class JudgeAgent:
    def __init__(self):
        self.client = Anthropic()

    def deliberate(self, crime) -> dict:
        case_file = f"""
Criminal: {crime.criminal}
Victim: {crime.victim}
Amount stolen: {crime.amount_stolen} tokens
Day of crime: Day {crime.day}
Prior offenses: {crime.prior_offenses}
"""
        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": JUDGE_PROMPT.format(case_file=case_file)
            }]
        )
        
        raw = response.content[0].text
        clean = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        
        return Verdict(
            guilty=data["guilty"],
            fine=data.get("fine", 0),
            exile_days=data.get("exile_days", 0),
            reasoning=data["reasoning"],
            judge_statement=data["judge_statement"]
        )