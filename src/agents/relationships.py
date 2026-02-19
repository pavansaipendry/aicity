"""
src/agents/relationships.py

Tracks bond strength between agents.
Bond scale: -1.0 (enemy) to +1.0 (close ally)
"""

from loguru import logger

BOND_EVENTS = {
    "collaborated": +0.15,
    "helped":       +0.20,
    "messaged":     +0.05,
    "taught":       +0.25,
    "healed":       +0.30,
    "stole_from":   -0.40,
    "arrested":     -0.35,
    "betrayed":     -0.50,
    "defended":     +0.20,
}


class RelationshipTracker:

    def __init__(self):
        self._bonds: dict[tuple, float] = {}

    def update(self, agent_a: str, agent_b: str, event: str):
        delta = BOND_EVENTS.get(event, 0.0)
        if delta == 0.0:
            return
        key = tuple(sorted([agent_a, agent_b]))
        current = self._bonds.get(key, 0.0)
        self._bonds[key] = max(-1.0, min(1.0, current + delta))
        logger.debug(f"🤝 Bond {agent_a}↔{agent_b}: {current:.2f} → {self._bonds[key]:.2f} ({event})")

    def get_bond(self, agent_a: str, agent_b: str) -> float:
        return self._bonds.get(tuple(sorted([agent_a, agent_b])), 0.0)

    def get_label(self, agent_a: str, agent_b: str) -> str:
        bond = self.get_bond(agent_a, agent_b)
        if bond >= 0.7:  return "close ally"
        if bond >= 0.4:  return "ally"
        if bond >= 0.15: return "friendly"
        if bond >= -0.1: return "neutral"
        if bond >= -0.4: return "tense"
        if bond >= -0.7: return "rival"
        return "enemy"

    def get_context_for_brain(self, agent_name: str, all_agents: list[dict]) -> str:
        """Inject this into the LLM brain prompt."""
        lines = []
        for other in all_agents:
            if other["name"] == agent_name:
                continue
            bond = self.get_bond(agent_name, other["name"])
            if abs(bond) > 0.1:
                label = self.get_label(agent_name, other["name"])
                lines.append(f"  - {other['name']} ({other['role']}): {label} [{bond:+.2f}]")
        if not lines:
            return "No strong bonds yet."
        return "Your relationships:\n" + "\n".join(lines)

    def decay(self, rate: float = 0.02):
        """Call once per day — bonds fade if not reinforced."""
        for key in self._bonds:
            self._bonds[key] *= (1 - rate)