"""
HomeManager — Phase 5
Manages home lot assignment, ownership tracking, and window-light state.
Shares the HOME_LOTS list with PositionManager.
"""

from loguru import logger
from src.city.position_manager import HOME_LOTS

HOME_PURCHASE_COST = 300   # tokens to buy a home lot
HOME_PURCHASE_MIN_TOKENS = 500  # agent must have at least this much first


class HomeManager:
    """
    Handles home purchases (agents with >500 tokens buy the next free lot for 300 tokens)
    and tracks which agents are home at night (for window light rendering).
    """

    def __init__(self) -> None:
        # Shared list — mutated in place so PositionManager.home_lots stays in sync
        self.lots: list[dict] = [lot.copy() for lot in HOME_LOTS]
        # agent_name → True if currently at home (updated each time_phase)
        self._at_home: dict[str, bool] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def check_home_purchases(
        self, agents: list, token_engine
    ) -> list[dict]:
        """
        Called once per day after agent turns.
        Any living agent with tokens > HOME_PURCHASE_MIN_TOKENS and no home claimed
        may purchase the next free lot for HOME_PURCHASE_COST tokens.

        Returns a list of home_claimed event dicts for WebSocket broadcast.
        """
        events: list[dict] = []

        for agent in agents:
            if agent.status != "alive":
                continue
            if agent.home_claimed:
                continue
            if agent.tokens < HOME_PURCHASE_MIN_TOKENS:
                continue

            lot = self._next_free_lot()
            if lot is None:
                logger.debug("[HomeManager] No free lots left in the city.")
                break

            # Deduct through token_engine — single source of truth for all balances
            if token_engine is None:
                continue
            paid = token_engine.spend(agent.id, HOME_PURCHASE_COST, "home_purchase")
            if not paid:
                continue
            # Sync in-memory balance with what token_engine now holds
            agent.tokens = token_engine.get_balance(agent.id)

            # Record ownership
            lot["owner"] = agent.name
            agent.home_tile_x = lot["x"]
            agent.home_tile_y = lot["y"]
            agent.home_claimed = True

            # Persist home columns to DB (separate from token_engine's agent_balances table)
            self._persist_home(agent, lot)

            logger.info(
                f"[HomeManager] {agent.name} purchased {lot['id']} at "
                f"({lot['x']}, {lot['y']}) for {HOME_PURCHASE_COST} tokens."
            )

            events.append({
                "type": "home_claimed",
                "agent": agent.name,
                "role": agent.role,
                "lot_id": lot["id"],
                "x": lot["x"],
                "y": lot["y"],
            })

        return events

    def get_home(self, agent_name: str) -> dict | None:
        """Returns the lot dict owned by agent_name, or None."""
        for lot in self.lots:
            if lot["owner"] == agent_name:
                return lot
        return None

    def set_at_home(self, agent_name: str, is_home: bool) -> None:
        """Called by city_v3.py during evening/night phase updates."""
        self._at_home[agent_name] = is_home

    def light_on(self, agent_name: str) -> bool:
        """
        Returns True if agent owns a home AND is currently at home.
        Used by the frontend to determine whether window lights should glow.
        """
        lot = self.get_home(agent_name)
        if lot is None:
            return False
        return self._at_home.get(agent_name, False)

    def lights_snapshot(self) -> list[dict]:
        """
        Returns a list of {lot_id, owner, light_on} dicts for all occupied lots.
        Sent in the `home_lights` WebSocket event each night phase.
        """
        result = []
        for lot in self.lots:
            if lot["owner"] is None:
                continue
            result.append({
                "lot_id": lot["id"],
                "owner": lot["owner"],
                "x": lot["x"],
                "y": lot["y"],
                "light_on": self.light_on(lot["owner"]),
            })
        return result

    # ── Internal ─────────────────────────────────────────────────────────────

    def _next_free_lot(self) -> dict | None:
        """Returns the first unowned lot, or None if all are taken."""
        for lot in self.lots:
            if lot["owner"] is None:
                return lot
        return None

    def _persist_home(self, agent, lot: dict) -> None:
        """
        Persists home lot ownership to the agents table so it survives restarts.
        Token deduction is already handled by token_engine — this only writes
        home_tile_x, home_tile_y, home_claimed columns.
        """
        try:
            import psycopg2
            from dotenv import load_dotenv
            import os as _os
            load_dotenv()
            db_url = _os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:password@localhost:5432/aicity"
            )
            with psycopg2.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE agents
                        SET home_tile_x = %s, home_tile_y = %s, home_claimed = TRUE
                        WHERE name = %s
                        """,
                        (lot["x"], lot["y"], agent.name),
                    )
        except Exception as e:
            logger.error(f"[HomeManager] DB persist failed for {agent.name}: {e}")
