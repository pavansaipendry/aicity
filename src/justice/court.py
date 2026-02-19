from dataclasses import dataclass
from typing import Optional
from loguru import logger
from src.justice.judge import Verdict

@dataclass
class CrimeReport:
    criminal: str
    victim: str
    amount_stolen: int
    day: int
    prior_offenses: int

# @dataclass  
# class Verdict:
#     guilty: bool
#     fine: int
#     exile_days: int
#     reasoning: str
#     judge_statement: str

class Court:
    """Processes criminal cases and delivers verdicts."""

    def __init__(self, judge_agent, transfer_engine):
        self.judge = judge_agent
        self.transfers = transfer_engine
        self.case_history = []

    def file_case(self, crime: CrimeReport):
        """Police calls this after arrest."""
        self.case_history.append(crime)
        logger.info(f"⚖️ Case filed: {crime.criminal} charged with theft of {crime.amount_stolen} tokens")

    def process_pending_cases(self, agents: dict) -> list[Verdict]:
        """Called once per day to process all pending cases."""
        verdicts = []
        pending = [c for c in self.case_history if not hasattr(c, 'resolved')]
        
        for crime in pending:
            verdict = self.judge.deliberate(crime)
            self._execute_sentence(crime, verdict, agents)
            crime.resolved = True
            verdicts.append(verdict)
        
        return verdicts

    def _execute_sentence(self, crime: CrimeReport, verdict: Verdict, agents: dict):
        if not verdict.guilty:
            logger.info(f"⚖️ {crime.criminal} found NOT GUILTY")
            return

        criminal = agents.get(crime.criminal)
        victim = agents.get(crime.victim)

        if verdict.fine > 0 and criminal and victim:
            # Pass names (strings), not Agent objects
            result = self.transfers.fine(criminal.name, victim.name, verdict.fine)
            logger.info(f"⚖️ {crime.criminal} fined {result.amount} tokens → paid to {crime.victim}")

        if verdict.exile_days > 0 and criminal:
            if hasattr(criminal, 'exiled_until'):
                criminal.exiled_until = criminal.age_days + verdict.exile_days
            logger.warning(f"⚖️ {crime.criminal} exiled for {verdict.exile_days} days")