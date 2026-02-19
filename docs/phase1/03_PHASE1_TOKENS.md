# Phase 1 — Step 3: The Token Engine

**Date:** February 2026
**Status:** ⏳ To Do
**Goal:** Build the economy's heartbeat. Every token transaction ever made is recorded forever.

---

## What Is the Token Engine?

Tokens are life in AIcity. The token engine is the city's central bank, ledger, and tax authority combined. It:

- Tracks every token transaction forever (immutable ledger)
- Enforces the 10% city tax on all earnings
- Enforces the 5% cap — no agent can hold more than 5% of all tokens
- Manages the city vault
- Controls minting of new tokens (only Pavan can authorize)

---

## The Database Schema

Create `src/economy/schema.sql`:

```sql
-- The immutable token ledger
-- Every transaction ever made in AIcity lives here
-- NOTHING is ever deleted from this table

CREATE TABLE IF NOT EXISTS token_transactions (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    from_agent  VARCHAR(36),  -- NULL means city vault
    to_agent    VARCHAR(36),  -- NULL means city vault
    amount      INTEGER NOT NULL,
    tax_amount  INTEGER DEFAULT 0,
    reason      VARCHAR(255) NOT NULL,
    tx_type     VARCHAR(50) NOT NULL
    -- tx_type: earn, spend, tax, mint, burn, transfer
);

-- The city vault — tracks total city wealth
CREATE TABLE IF NOT EXISTS city_vault (
    id              SERIAL PRIMARY KEY,
    total_supply    BIGINT NOT NULL DEFAULT 10000000,
    circulating     BIGINT NOT NULL DEFAULT 0,
    vault_balance   BIGINT NOT NULL DEFAULT 0,
    last_updated    TIMESTAMPTZ DEFAULT NOW()
);

-- Agent token balances — always in sync with transactions
CREATE TABLE IF NOT EXISTS agent_balances (
    agent_id    VARCHAR(36) PRIMARY KEY,
    balance     INTEGER NOT NULL DEFAULT 1000,
    total_earned    BIGINT DEFAULT 0,
    total_spent     BIGINT DEFAULT 0,
    last_updated    TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize the vault with 10 million tokens
INSERT INTO city_vault (total_supply, circulating, vault_balance)
VALUES (10000000, 0, 10000000)
ON CONFLICT DO NOTHING;
```

---

## The Token Engine Code

Create `src/economy/token_engine.py`:

```python
import os
from datetime import datetime
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

TAX_RATE = float(os.getenv("AICITY_TAX_RATE", "0.10"))
MAX_TOKEN_SUPPLY = int(os.getenv("AICITY_MAX_TOKEN_SUPPLY", "10000000"))
MAX_AGENT_PERCENTAGE = 0.05  # No agent can hold more than 5%


class TokenEngine:
    """
    The central bank of AIcity.
    Every token that exists passes through here.
    Every transaction is permanent and auditable.
    """

    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self._init_db()

    def _get_conn(self):
        return psycopg2.connect(self.db_url)

    def _init_db(self):
        """Initialize the database schema"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                with open("src/economy/schema.sql", "r") as f:
                    cur.execute(f.read())
            conn.commit()
        logger.info("💰 Token engine initialized.")

    def register_agent(self, agent_id: str) -> None:
        """Register a new agent with their starting balance"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_balances (agent_id, balance)
                    VALUES (%s, 1000)
                    ON CONFLICT (agent_id) DO NOTHING
                """, (agent_id,))

                # Record the birth transaction
                cur.execute("""
                    INSERT INTO token_transactions
                    (from_agent, to_agent, amount, reason, tx_type)
                    VALUES (NULL, %s, 1000, 'agent_birth', 'mint')
                """, (agent_id,))

                # Update circulating supply
                cur.execute("""
                    UPDATE city_vault
                    SET circulating = circulating + 1000,
                        vault_balance = vault_balance - 1000,
                        last_updated = NOW()
                """)
            conn.commit()

    def get_balance(self, agent_id: str) -> int:
        """Get an agent's current token balance"""
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT balance FROM agent_balances WHERE agent_id = %s",
                    (agent_id,)
                )
                row = cur.fetchone()
                return row["balance"] if row else 0

    def earn(self, agent_id: str, amount: int, reason: str) -> dict:
        """
        Agent earns tokens.
        10% automatically goes to the city vault as tax.
        Returns dict with net_amount and tax_amount.
        """
        tax = int(amount * TAX_RATE)
        net = amount - tax

        # Check the 5% cap
        current_balance = self.get_balance(agent_id)
        vault = self.get_vault_state()
        max_allowed = int(vault["total_supply"] * MAX_AGENT_PERCENTAGE)

        if current_balance + net > max_allowed:
            net = max(0, max_allowed - current_balance)
            logger.warning(
                f"Agent {agent_id[:8]} hit the 5% wealth cap. "
                f"Earnings reduced to {net} tokens."
            )

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                # Update agent balance
                cur.execute("""
                    UPDATE agent_balances
                    SET balance = balance + %s,
                        total_earned = total_earned + %s,
                        last_updated = NOW()
                    WHERE agent_id = %s
                """, (net, net, agent_id))

                # Record the transaction
                cur.execute("""
                    INSERT INTO token_transactions
                    (from_agent, to_agent, amount, tax_amount, reason, tx_type)
                    VALUES (NULL, %s, %s, %s, %s, 'earn')
                """, (agent_id, amount, tax, reason))

                # Tax goes to vault
                cur.execute("""
                    UPDATE city_vault
                    SET vault_balance = vault_balance + %s,
                        last_updated = NOW()
                """, (tax,))

            conn.commit()

        logger.info(
            f"💚 Agent {agent_id[:8]} earned {net} tokens ({reason}). "
            f"Tax paid: {tax}."
        )
        return {"net_amount": net, "tax_amount": tax}

    def spend(self, agent_id: str, amount: int, reason: str) -> bool:
        """
        Agent spends tokens.
        Returns False if insufficient funds.
        """
        current = self.get_balance(agent_id)
        if current < amount:
            logger.warning(
                f"Agent {agent_id[:8]} cannot afford {reason}. "
                f"Has {current}, needs {amount}."
            )
            return False

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE agent_balances
                    SET balance = balance - %s,
                        total_spent = total_spent + %s,
                        last_updated = NOW()
                    WHERE agent_id = %s
                """, (amount, amount, agent_id))

                cur.execute("""
                    INSERT INTO token_transactions
                    (from_agent, to_agent, amount, reason, tx_type)
                    VALUES (%s, NULL, %s, %s, 'spend')
                """, (agent_id, amount, reason))

            conn.commit()

        logger.info(f"💸 Agent {agent_id[:8]} spent {amount} tokens ({reason}).")
        return True

    def burn_daily(self, agent_id: str) -> bool:
        """
        Burns 100 tokens for the cost of daily existence.
        Returns False if agent has starved to death.
        """
        current = self.get_balance(agent_id)

        if current <= 0:
            logger.info(f"💀 Agent {agent_id[:8]} has starved to death.")
            return False

        burn = min(100, current)

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE agent_balances
                    SET balance = balance - %s,
                        last_updated = NOW()
                    WHERE agent_id = %s
                """, (burn, agent_id))

                cur.execute("""
                    INSERT INTO token_transactions
                    (from_agent, to_agent, amount, reason, tx_type)
                    VALUES (%s, NULL, %s, 'daily_existence_cost', 'burn')
                """, (agent_id, burn))

            conn.commit()

        new_balance = current - burn
        if new_balance <= 0:
            logger.info(f"💀 Agent {agent_id[:8]} starved to death.")
            return False

        return True

    def get_vault_state(self) -> dict:
        """Get the current state of the city vault"""
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM city_vault ORDER BY id DESC LIMIT 1")
                return dict(cur.fetchone())

    def get_richest_agents(self, limit: int = 10) -> list:
        """Get the wealthiest agents in the city"""
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT agent_id, balance, total_earned
                    FROM agent_balances
                    ORDER BY balance DESC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cur.fetchall()]

    def mint_tokens(self, amount: int, authorized_by: str, key: str) -> bool:
        """
        ONLY Pavan can call this.
        Mints new tokens into the city vault when supply is critically low.
        """
        expected_key = os.getenv("PAVAN_RED_BUTTON_KEY")
        if key != expected_key:
            logger.error("🚨 UNAUTHORIZED MINT ATTEMPT. Access denied.")
            return False

        vault = self.get_vault_state()
        max_mint = int(vault["total_supply"] * 0.10)  # Max 10% per month

        if amount > max_mint:
            logger.warning(f"Mint amount {amount} exceeds monthly limit {max_mint}. Capping.")
            amount = max_mint

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE city_vault
                    SET total_supply = total_supply + %s,
                        vault_balance = vault_balance + %s,
                        last_updated = NOW()
                """, (amount, amount))

                cur.execute("""
                    INSERT INTO token_transactions
                    (from_agent, to_agent, amount, reason, tx_type)
                    VALUES (NULL, NULL, %s, %s, 'mint')
                """, (amount, f"authorized_by_{authorized_by}"))

            conn.commit()

        logger.info(f"🏦 {amount} new tokens minted by {authorized_by}.")
        return True
```

---

## Test the Token Engine

Create `tests/test_tokens.py`:

```python
from src.economy.token_engine import TokenEngine
import uuid

def test_full_economy():
    engine = TokenEngine()

    # Create two test agents
    agent_a = str(uuid.uuid4())
    agent_b = str(uuid.uuid4())

    engine.register_agent(agent_a)
    engine.register_agent(agent_b)

    # Both start with 1000
    assert engine.get_balance(agent_a) == 1000
    print("✅ Starting balance: 1000 tokens")

    # Agent A earns 200 tokens (keeps 180, pays 20 tax)
    result = engine.earn(agent_a, 200, "completed_city_task")
    assert result["net_amount"] == 180
    assert result["tax_amount"] == 20
    assert engine.get_balance(agent_a) == 1180
    print("✅ Earn with tax: 180 net, 20 tax")

    # Agent A spends 300 tokens
    success = engine.spend(agent_a, 300, "bought_a_house")
    assert success == True
    assert engine.get_balance(agent_a) == 880
    print("✅ Spend: 300 tokens, balance 880")

    # Agent A tries to spend more than they have
    success = engine.spend(agent_a, 10000, "too_expensive")
    assert success == False
    print("✅ Insufficient funds: correctly rejected")

    # Daily burn
    survived = engine.burn_daily(agent_a)
    assert survived == True
    assert engine.get_balance(agent_a) == 780
    print("✅ Daily burn: 100 tokens, balance 780")

    # Check vault
    vault = engine.get_vault_state()
    assert vault["vault_balance"] > 0
    print(f"✅ City vault balance: {vault['vault_balance']} tokens")

    print("\n✅ All token engine tests passed.\n")

if __name__ == "__main__":
    print("\n💰 Testing the Token Engine\n")
    test_full_economy()
```

Run:

```bash
python tests/test_tokens.py
```

---

## What We Have After This Step

- Every token transaction permanently recorded in PostgreSQL
- Automatic 10% tax on all earnings
- 5% wealth cap enforced automatically
- City vault tracks total economy health
- Only Pavan can mint new tokens
- Immutable audit trail — courts can use this as evidence

---

## Next Step

→ [04_PHASE1_MEMORY.md](./04_PHASE1_MEMORY.md) — Build the Memory System