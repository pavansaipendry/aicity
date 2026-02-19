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

    def deduct(self, agent_id: str, amount: int, reason: str) -> int:
        """
        One-sided deduction — used when an agent is a theft victim.
        No tax, no wealth cap. Floors at 100 (MIN_BALANCE).
        Returns the actual amount deducted.
        """
        current = self.get_balance(agent_id)
        actual = min(amount, max(0, current - 100))
        if actual <= 0:
            return 0

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE agent_balances
                    SET balance = balance - %s, last_updated = NOW()
                    WHERE agent_id = %s
                """, (actual, agent_id))
                cur.execute("""
                    INSERT INTO token_transactions
                    (from_agent, to_agent, amount, reason, tx_type)
                    VALUES (%s, NULL, %s, %s, 'deduct')
                """, (agent_id, actual, reason))
            conn.commit()

        logger.info(f"💸 Deducted {actual} tokens from {agent_id[:8]} ({reason}).")
        return actual

    def transfer(self, from_id: str, to_id: str, amount: int, reason: str) -> int:
        """
        Atomic bilateral transfer — used for court fines and trades.
        No tax. Floors sender at 100 (MIN_BALANCE).
        Returns the actual amount transferred.
        """
        current = self.get_balance(from_id)
        actual = min(amount, max(0, current - 100))
        if actual <= 0:
            return 0

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE agent_balances
                    SET balance = balance - %s, last_updated = NOW()
                    WHERE agent_id = %s
                """, (actual, from_id))
                cur.execute("""
                    UPDATE agent_balances
                    SET balance = balance + %s, last_updated = NOW()
                    WHERE agent_id = %s
                """, (actual, to_id))
                cur.execute("""
                    INSERT INTO token_transactions
                    (from_agent, to_agent, amount, reason, tx_type)
                    VALUES (%s, %s, %s, %s, 'transfer')
                """, (from_id, to_id, actual, reason))
            conn.commit()

        logger.info(f"💸 Transfer {from_id[:8]} → {to_id[:8]}: {actual} tokens ({reason}).")
        return actual

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