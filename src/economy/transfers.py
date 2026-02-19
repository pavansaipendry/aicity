"""
src/economy/transfers.py

Real bilateral token transfers for Phase 3.

In Phase 2, theft was one-sided: thief gained tokens, victim unchanged.
In Phase 3, TransferEngine moves tokens between actual agent objects.

Usage in city_v3.py:
    transfer_engine = TransferEngine(agents)   # pass list of agent dicts
    execute_action(agent, decision, all_agents, day, transfer_engine)

Usage for court fines:
    transfer_engine.fine("Delta-Dawn", "Kappa-Root", 200)
"""

from dataclasses import dataclass
from loguru import logger


@dataclass
class TransferResult:
    success: bool
    amount: int
    from_agent: str
    to_agent: str
    reason: str
    from_balance_after: int
    to_balance_after: int


class TransferEngine:

    MIN_BALANCE = 100  # matches daily burn — no agent drained below survival floor

    def __init__(self, agents: list[dict], token_engine=None):
        """
        agents: the same list[dict] used by city_v3.
        Each dict must have "name", "id", and "tokens" keys.
        Tokens are mutated in place for LLM context accuracy.
        token_engine: TokenEngine instance — required for DB persistence.
        """
        self._agents = {a["name"]: a for a in agents}
        self._token_engine = token_engine

    def update_agents(self, agents: list[dict]):
        """Call at the start of each day and after births so dicts stay current."""
        self._agents = {a["name"]: a for a in agents}

    # ── Public methods ────────────────────────────────────────────

    def steal(self, thief_name: str, victim_name: str, intended: int) -> TransferResult:
        """
        Thief steals from victim. Victim actually loses tokens in DB.
        The thief's credit is handled separately by token_engine.earn() in city_v3,
        so we only deduct the victim here (credit_receiver=False).
        """
        return self._transfer(victim_name, thief_name, intended, "theft", credit_receiver=False)

    def fine(self, criminal_name: str, victim_name: str, amount: int) -> TransferResult:
        """Court fine: criminal pays victim (or police if victim is dead)."""
        if victim_name not in self._agents:
            police = next(
                (name for name, a in self._agents.items()
                 if a.get("role") == "police" and a.get("status") == "alive"),
                None
            )
            if police:
                logger.info(f"⚖️ Victim {victim_name} gone — fine redirected to {police}")
                return self._transfer(criminal_name, police, amount, "court_fine", credit_receiver=True)
            return self._failed(criminal_name, victim_name, "court_fine")
        return self._transfer(criminal_name, victim_name, amount, "court_fine", credit_receiver=True)

    def trade(self, buyer_name: str, seller_name: str, amount: int) -> TransferResult:
        """Voluntary trade between two agents."""
        return self._transfer(buyer_name, seller_name, amount, "trade", credit_receiver=True)

    # ── Internal ──────────────────────────────────────────────────

    def _transfer(
        self,
        from_name: str,
        to_name: str,
        amount: int,
        reason: str,
        credit_receiver: bool = True,
    ) -> TransferResult:
        sender = self._agents.get(from_name)
        receiver = self._agents.get(to_name)

        if not sender or not receiver:
            logger.warning(f"⚠️ Transfer failed — agent not found: {from_name} → {to_name}")
            return self._failed(from_name, to_name, reason)

        transferable = sender["tokens"] - self.MIN_BALANCE
        actual = min(amount, max(0, transferable))

        if actual <= 0:
            logger.info(f"💸 Skipped: {from_name} only has {sender['tokens']} tokens (floor={self.MIN_BALANCE})")
            return TransferResult(
                success=False, amount=0,
                from_agent=from_name, to_agent=to_name, reason=reason,
                from_balance_after=sender["tokens"],
                to_balance_after=receiver["tokens"],
            )

        # ── Persist to DB ──────────────────────────────────────────
        if self._token_engine:
            sender_id = sender.get("id")
            receiver_id = receiver.get("id")
            if credit_receiver and sender_id and receiver_id:
                # Bidirectional: fine / trade — atomic DB transfer
                actual = self._token_engine.transfer(sender_id, receiver_id, actual, reason)
            elif sender_id:
                # One-sided: theft — only deduct victim; thief earns via token_engine.earn()
                actual = self._token_engine.deduct(sender_id, actual, reason)

        if actual <= 0:
            return TransferResult(
                success=False, amount=0,
                from_agent=from_name, to_agent=to_name, reason=reason,
                from_balance_after=sender["tokens"],
                to_balance_after=receiver["tokens"],
            )

        # ── Sync in-memory dicts so LLM context stays accurate ────
        sender["tokens"] -= actual
        if credit_receiver:
            receiver["tokens"] += actual

        logger.info(
            f"💸 {reason.upper()}: {from_name} → {to_name} | "
            f"{actual} tokens | "
            f"{from_name}: {sender['tokens'] + actual}→{sender['tokens']} | "
            f"{to_name}: {receiver['tokens'] - (actual if credit_receiver else 0)}→{receiver['tokens']}"
        )

        return TransferResult(
            success=True, amount=actual,
            from_agent=from_name, to_agent=to_name, reason=reason,
            from_balance_after=sender["tokens"],
            to_balance_after=receiver["tokens"],
        )

    def _failed(self, from_name: str, to_name: str, reason: str) -> TransferResult:
        s = self._agents.get(from_name, {})
        r = self._agents.get(to_name, {})
        return TransferResult(
            success=False, amount=0,
            from_agent=from_name, to_agent=to_name, reason=reason,
            from_balance_after=s.get("tokens", 0),
            to_balance_after=r.get("tokens", 0),
        )