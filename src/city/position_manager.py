"""
PositionManager — Phase 5
Manages agent tile positions, home assignment, zone routing, and patrol waypoints.
All coordinates are in tile units (col, row) matching the 96×72 city map.
"""

import random
from typing import Optional

from loguru import logger

# ── Zone definitions ────────────────────────────────────────────────────────
# Each zone is (x1, y1, x2, y2) in tile coordinates (inclusive bounding box)

ZONES: dict[str, tuple[int, int, int, int]] = {
    "LOC_WILDERNESS_N":      (0,  0,  96, 12),
    "LOC_RIVER":             (3,  0,   6, 72),
    "LOC_BRIDGE":            (3, 20,   6, 23),
    "LOC_RESIDENTIAL_N":     (18, 14, 58, 26),
    "LOC_TOWN_SQUARE":       (28, 26, 52, 34),
    "LOC_MARKET":            (8,  32, 28, 44),
    "LOC_POLICE_STATION":    (54, 30, 68, 40),
    "LOC_BUILDER_YARD":      (64, 14, 82, 28),
    "LOC_CLINIC":            (8,  44, 22, 56),
    "LOC_RESIDENTIAL_S":     (28, 44, 58, 56),
    "LOC_SCHOOL":            (62, 44, 80, 56),
    "LOC_ARCHIVE":           (8,  58, 22, 68),
    "LOC_VAULT":             (30, 58, 44, 68),
    "LOC_DARK_ALLEY":        (64, 58, 82, 68),
    "LOC_WHISPERING_CAVES":  (84, 62, 96, 72),
    "LOC_OUTSKIRTS_E":       (82, 14, 96, 58),
    "LOC_EXPLORATION_TRAIL": (20,  0, 96, 14),
}

# ── Role → default work zone ─────────────────────────────────────────────────

WORK_ZONES: dict[str, str] = {
    "builder":     "LOC_BUILDER_YARD",
    "explorer":    "LOC_EXPLORATION_TRAIL",
    "police":      "LOC_POLICE_STATION",
    "merchant":    "LOC_MARKET",
    "teacher":     "LOC_SCHOOL",
    "healer":      "LOC_CLINIC",
    "messenger":   "LOC_TOWN_SQUARE",
    "lawyer":      "LOC_VAULT",
    "thief":       "LOC_DARK_ALLEY",
    "newborn":     "LOC_SCHOOL",
    "gang_leader": "LOC_DARK_ALLEY",
    "blackmailer": "LOC_DARK_ALLEY",
    "saboteur":    "LOC_BUILDER_YARD",
}

# Police patrol loop: Station → Market → Alley → Square → Station
PATROL_WAYPOINTS: list[tuple[float, float]] = [
    (61.0, 35.0),   # Police station exit
    (18.0, 38.0),   # Market district
    (73.0, 63.0),   # Dark alley
    (40.0, 30.0),   # Town square
    (61.0, 35.0),   # Back to station
]

# Home lots defined in plan section 6e — residential N (01-06) and S (07-10)
HOME_LOTS: list[dict] = [
    {"id": "home_01", "x": 20, "y": 16, "owner": None},
    {"id": "home_02", "x": 26, "y": 16, "owner": None},
    {"id": "home_03", "x": 32, "y": 16, "owner": None},
    {"id": "home_04", "x": 38, "y": 16, "owner": None},
    {"id": "home_05", "x": 44, "y": 16, "owner": None},
    {"id": "home_06", "x": 50, "y": 16, "owner": None},
    {"id": "home_07", "x": 30, "y": 47, "owner": None},
    {"id": "home_08", "x": 36, "y": 47, "owner": None},
    {"id": "home_09", "x": 42, "y": 47, "owner": None},
    {"id": "home_10", "x": 48, "y": 47, "owner": None},
]


class PositionManager:
    """
    Tracks and routes all agent positions across the 96×72 tile city map.

    Usage:
        pm = PositionManager()
        pm.assign_starting_positions(agents)
        dest = pm.get_work_destination(agent, time_phase="morning")
    """

    def __init__(self) -> None:
        # agent_name → current (x, y) tile position
        self._positions: dict[str, tuple[float, float]] = {}
        # Copy of home lots so HomeManager can share or replace this
        self.home_lots: list[dict] = [lot.copy() for lot in HOME_LOTS]

    # ── Public API ────────────────────────────────────────────────────────────

    def assign_starting_positions(self, agents: list) -> None:
        """
        Called at big_bang or server startup.
        Each agent gets a random starting tile inside their work zone.
        """
        for agent in agents:
            role = agent.role if isinstance(agent.role, str) else agent.role.value
            zone_id = WORK_ZONES.get(role, "LOC_TOWN_SQUARE")
            x, y = self._random_in_zone(zone_id)
            agent.x = x
            agent.y = y
            self._positions[agent.name] = (x, y)
            logger.debug(f"[Position] {agent.name} ({role}) starts at ({x:.1f}, {y:.1f}) [{zone_id}]")

    def assign_home(self, agent, tokens_threshold: int = 500) -> bool:
        """
        If agent has enough tokens and no home yet → claim the next free lot.
        Updates agent.home_tile_x/y and agent.home_claimed.
        Returns True if a home was assigned.
        """
        if agent.home_claimed:
            return False
        if agent.tokens < tokens_threshold:
            return False

        for lot in self.home_lots:
            if lot["owner"] is None:
                lot["owner"] = agent.name
                agent.home_tile_x = lot["x"]
                agent.home_tile_y = lot["y"]
                agent.home_claimed = True
                logger.info(
                    f"[Home] {agent.name} claimed {lot['id']} at "
                    f"({lot['x']}, {lot['y']})"
                )
                return True

        logger.debug(f"[Home] No free lots available for {agent.name}")
        return False

    def get_work_destination(self, agent, time_phase: str) -> tuple[float, float]:
        """
        Returns the target (x, y) tile for an agent based on role and time of day.

        - dawn:      return to home tile (or zone center if no home)
        - morning:   move to work zone
        - afternoon: stay in work zone (slight wander)
        - evening:   begin walking home
        - night:     at home (criminals: dark alley / caves)
        """
        role = agent.role if isinstance(agent.role, str) else agent.role.value

        if time_phase == "dawn":
            return self._home_or_zone(agent, role)

        if time_phase in ("evening", "night"):
            # Criminals stay active in dark zones at night
            if role in ("thief", "gang_leader", "blackmailer") and time_phase == "night":
                return self._random_in_zone("LOC_DARK_ALLEY")
            return self._home_or_zone(agent, role)

        # morning / afternoon → work zone
        zone_id = WORK_ZONES.get(role, "LOC_TOWN_SQUARE")
        return self._random_in_zone(zone_id)

    def get_patrol_waypoints(self, step: int) -> tuple[float, float]:
        """Returns the (x, y) tile for step N in the police patrol loop."""
        return PATROL_WAYPOINTS[step % len(PATROL_WAYPOINTS)]

    def get_zone_center(self, zone_id: str) -> tuple[float, float]:
        """Returns the center tile (x, y) of a named zone."""
        if zone_id not in ZONES:
            logger.warning(f"[Position] Unknown zone: {zone_id}, defaulting to Town Square")
            zone_id = "LOC_TOWN_SQUARE"
        x1, y1, x2, y2 = ZONES[zone_id]
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def update_position(self, agent_name: str, x: float, y: float) -> None:
        """Record a new tile position for an agent."""
        self._positions[agent_name] = (x, y)

    def get_position(self, agent_name: str) -> Optional[tuple[float, float]]:
        """Returns the last known (x, y) for an agent, or None."""
        return self._positions.get(agent_name)

    def agents_at_same_zone(
        self, agent_a_name: str, agent_b_name: str, radius: float = 5.0
    ) -> bool:
        """
        Returns True if two agents are within `radius` tiles of each other.
        Used by MeetingManager for proximity checks.
        """
        pos_a = self._positions.get(agent_a_name)
        pos_b = self._positions.get(agent_b_name)
        if pos_a is None or pos_b is None:
            return False
        dx = pos_a[0] - pos_b[0]
        dy = pos_a[1] - pos_b[1]
        dist = (dx * dx + dy * dy) ** 0.5
        return dist <= radius

    def which_zone(self, agent_name: str) -> Optional[str]:
        """Returns the zone ID that contains the agent's current position."""
        pos = self._positions.get(agent_name)
        if pos is None:
            return None
        x, y = pos
        for zone_id, (x1, y1, x2, y2) in ZONES.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return zone_id
        return None

    def snapshot(self) -> list[dict]:
        """
        Returns a list of position dicts suitable for the `positions` WebSocket event.
        """
        return [
            {"name": name, "x": pos[0], "y": pos[1]}
            for name, pos in self._positions.items()
        ]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _random_in_zone(self, zone_id: str) -> tuple[float, float]:
        """Returns a random tile within the given zone bounding box."""
        if zone_id not in ZONES:
            zone_id = "LOC_TOWN_SQUARE"
        x1, y1, x2, y2 = ZONES[zone_id]
        x = random.uniform(x1 + 1, x2 - 1)
        y = random.uniform(y1 + 1, y2 - 1)
        return (round(x, 1), round(y, 1))

    def _home_or_zone(self, agent, role: str) -> tuple[float, float]:
        """
        Returns agent's home tile if they own one, otherwise work zone center.
        Used for dawn/evening when agents return home.
        """
        if agent.home_claimed and agent.home_tile_x > 0:
            return (float(agent.home_tile_x), float(agent.home_tile_y))
        # No home yet — return to default zone
        zone_id = WORK_ZONES.get(role, "LOC_TOWN_SQUARE")
        return self.get_zone_center(zone_id)
