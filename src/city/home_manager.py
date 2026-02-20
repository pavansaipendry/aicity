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

            # Deduct tokens — use spend_tokens which logs and validates
            paid = agent.spend_tokens(HOME_PURCHASE_COST, f"buying home {lot['id']}")
            if not paid:
                continue

            # Record ownership
            lot["owner"] = agent.name
            agent.home_tile_x = lot["x"]
            agent.home_tile_y = lot["y"]
            agent.home_claimed = True

            # Persist to DB
            if token_engine is not None:
                try:
                    token_engine.conn.execute(
                        """
                        UPDATE agents
                        SET home_tile_x = %s, home_tile_y = %s, home_claimed = TRUE
                        WHERE name = %s
                        """,
                        (lot["x"], lot["y"], agent.name),
                    )
                    token_engine.conn.commit()
                except Exception as e:
                    logger.error(f"[HomeManager] DB update failed for {agent.name}: {e}")

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
