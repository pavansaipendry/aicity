# Feature 1 — Real Token Transfers

> **Priority:** 🔴 Critical  
> **Complexity:** Low  
> **Unlocks:** Trial System, meaningful economy

---

## Problem

In Phase 2, when the thief steals, only the thief gains tokens. The victim's balance is unchanged. This makes the economy purely additive — there are no real losers, no actual stakes.

```python
# Phase 2 (broken)
thief_agent.tokens += stolen_amount      # thief gains
# victim unchanged — stealing is free money from the vault
```

## Solution

Implement bilateral token transfers. When an agent steals, trades, or receives a fine — tokens move from one agent to another. The total in the system stays constant (minus tax).

```python
# Phase 3 (real)
def steal(thief, victim, amount):
    actual = min(amount, victim.tokens - 100)  # can't leave victim with 0
    if actual <= 0:
        return 0
    victim.tokens -= actual
    thief.tokens += actual
    return actual
```

---

## Implementation

### `src/economy/transfers.py` (new file)

```python
from dataclasses import dataclass
from typing import Optional
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
    """Handles all bilateral token transfers between agents."""

    MIN_BALANCE = 50  # agents can't be drained below this

    def transfer(self, from_agent, to_agent, amount: int, reason: str) -> TransferResult:
        """Move tokens from one agent to another."""
        actual = min(amount, from_agent.tokens - self.MIN_BALANCE)
        if actual <= 0:
            return TransferResult(
                success=False, amount=0,
                from_agent=from_agent.name, to_agent=to_agent.name,
                reason=reason, 
                from_balance_after=from_agent.tokens,
                to_balance_after=to_agent.tokens
            )
        
        from_agent.tokens -= actual
        to_agent.tokens += actual
        
        logger.info(f"💸 Transfer: {from_agent.name} → {to_agent.name}: {actual} tokens ({reason})")
        
        return TransferResult(
            success=True, amount=actual,
            from_agent=from_agent.name, to_agent=to_agent.name,
            reason=reason,
            from_balance_after=from_agent.tokens,
            to_balance_after=to_agent.tokens
        )

    def steal(self, thief, victim, intended_amount: int) -> TransferResult:
        return self.transfer(thief, victim, intended_amount, "theft")

    def fine(self, criminal, vault_agent, amount: int) -> TransferResult:
        return self.transfer(criminal, vault_agent, amount, "court_fine")

    def trade(self, buyer, seller, amount: int) -> TransferResult:
        return self.transfer(buyer, seller, amount, "trade")
```

### Changes to `behaviors.py`

The thief behavior needs to call the transfer engine instead of just earning:

```python
# behaviors.py — thief action
def thief_action(agent, city, transfer_engine):
    target = city.get_richest_agent(exclude=agent)
    intended = random.randint(50, 200)
    
    result = transfer_engine.steal(agent, target, intended)
    
    if result.success:
        # Log the actual victim's loss
        logger.info(f"🗡️ {agent.name} stole {result.amount} from {target.name}")
        city.report_crime(agent, target, result.amount)  # triggers potential arrest
    
    return result.amount
```

---

## Economic Impact

Once real transfers are live:

- **Merchant wealth compounds** — trading partners give real tokens
- **Theft creates real victims** — Kappa-Drift would have 400+ fewer tokens by Day 30
- **Inequality grows faster** — rich agents accumulate; poor agents get poorer
- **Gini coefficient becomes meaningful** — can track real wealth concentration

---

## Edge Cases

| Scenario | Handling |
|----------|---------|
| Victim has < 50 tokens | Transfer amount reduced to preserve minimum |
| Victim is dead | Cannot steal from dead agents |
| Thief has 0 tokens | Can still steal (no outgoing payment) |
| Court fine exceeds criminal balance | Fine reduced to available balance |

---

## Testing

```python
# test_transfers.py
def test_real_theft():
    thief = Agent("Iota-Root", role="thief", tokens=500)
    victim = Agent("Kappa-Drift", role="merchant", tokens=2000)
    engine = TransferEngine()
    
    result = engine.steal(thief, victim, 200)
    
    assert result.success == True
    assert result.amount == 200
    assert thief.tokens == 700      # gained
    assert victim.tokens == 1800   # lost
    assert thief.tokens + victim.tokens == 2500  # conserved
```

---

*This is the most impactful single change in Phase 3. Everything else builds on real economic stakes.*