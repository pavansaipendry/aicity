"""
src/city/action_router.py — Phase 5

Maps LLM action text → destination zone ID.

Used in Sprint 3 by AgentManager.js (via the positions WebSocket event) to
physically move agent sprites to where their decision sends them.

Backend usage (city_v3.py, Sprint 3):
    from src.city.action_router import route_action_to_destination
    dest = route_action_to_destination(agent.role, decision["action"])
    # dest is one of:
    #   - A LOC_* zone ID string → move sprite to that zone's center
    #   - "PATROL_ROUTE"         → follow the police patrol waypoint loop
    #   - "TARGET_AGENT"         → move toward the named target agent
    #   - "TARGET_ASSET"         → move toward nearest city asset
"""

from src.city.position_manager import WORK_ZONES

# ── Keyword → destination mapping ─────────────────────────────────────────────
# Order matters: more specific keywords should come before generic ones.

ACTION_TO_DESTINATION: dict[str, str] = {
    # Builder
    "build":         "LOC_BUILDER_YARD",
    "construct":     "LOC_BUILDER_YARD",
    "work on":       "LOC_BUILDER_YARD",
    "collaborate":   "LOC_BUILDER_YARD",
    "scaffold":      "LOC_BUILDER_YARD",
    # Explorer
    "explore":       "LOC_EXPLORATION_TRAIL",
    "venture":       "LOC_EXPLORATION_TRAIL",
    "discover":      "LOC_EXPLORATION_TRAIL",
    "survey":        "LOC_EXPLORATION_TRAIL",
    "map the":       "LOC_EXPLORATION_TRAIL",
    # Police
    "patrol":        "PATROL_ROUTE",
    "investigate":   "LOC_POLICE_STATION",
    "file a report": "LOC_POLICE_STATION",
    "arrest":        "TARGET_AGENT",
    # Merchant
    "sell":          "LOC_MARKET",
    "trade":         "LOC_MARKET",
    "negotiate":     "LOC_MARKET",
    "open stall":    "LOC_MARKET",
    "market":        "LOC_MARKET",
    # Teacher
    "teach":         "LOC_SCHOOL",
    "mentor":        "LOC_SCHOOL",
    "lesson":        "LOC_SCHOOL",
    "educate":       "LOC_SCHOOL",
    # Healer
    "heal":          "TARGET_AGENT",
    "treat":         "LOC_CLINIC",
    "tend":          "LOC_CLINIC",
    "diagnose":      "LOC_CLINIC",
    "clinic":        "LOC_CLINIC",
    # Messenger
    "deliver":       "LOC_TOWN_SQUARE",
    "post the":      "LOC_TOWN_SQUARE",
    "publish":       "LOC_TOWN_SQUARE",
    "write the":     "LOC_TOWN_SQUARE",
    # Lawyer
    "file the case": "LOC_VAULT",
    "courthouse":    "LOC_VAULT",
    "defend":        "LOC_VAULT",
    # Thief
    "steal":         "TARGET_AGENT",
    "rob":           "TARGET_AGENT",
    "pickpocket":    "TARGET_AGENT",
    "snatch":        "TARGET_AGENT",
    # Gang leader
    "recruit":       "TARGET_AGENT",
    "organize":      "LOC_DARK_ALLEY",
    "gang":          "LOC_DARK_ALLEY",
    # Blackmailer
    "blackmail":     "TARGET_AGENT",
    "extort":        "TARGET_AGENT",
    "threaten":      "LOC_WHISPERING_CAVES",
    "whispering":    "LOC_WHISPERING_CAVES",
    "caves":         "LOC_WHISPERING_CAVES",
    # Saboteur
    "sabotage":      "TARGET_ASSET",
    "destroy":       "TARGET_ASSET",
    "demolish":      "TARGET_ASSET",
    "burn":          "TARGET_ASSET",
    "damage":        "TARGET_ASSET",
}


def route_action_to_destination(
    agent_role: str,
    action: str,
    context: dict | None = None,
) -> str:
    """
    Parse an LLM action string and return a destination zone or special token.

    Returns:
        LOC_* str         — move to that zone's center tile
        "PATROL_ROUTE"    — follow the police patrol waypoint loop
        "TARGET_AGENT"    — move toward context["target_agent"] (str name)
        "TARGET_ASSET"    — move toward nearest standing asset

    Falls back to the role's default work zone if no keyword matches.
    """
    action_lower = action.lower()
    for keyword, destination in ACTION_TO_DESTINATION.items():
        if keyword in action_lower:
            return destination
    # Default: role's registered work zone, or Town Square if unknown
    return WORK_ZONES.get(agent_role, "LOC_TOWN_SQUARE")
