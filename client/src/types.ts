/**
 * types.ts — shared TypeScript interfaces for AIcity Phase 6
 *
 * These mirror the Python data structures sent over WebSocket.
 * If you change the Python backend, update these too.
 */

// ── Tile layer constants ────────────────────────────────────────────────────
export const LAYER_GROUND    = 0; // water, dirt, sand
export const LAYER_ROAD      = 1; // roads, paths
export const LAYER_NATURE    = 2; // trees, rocks, bushes
export const LAYER_BUILDING  = 3; // structures

/** One tile in the world_tiles table. */
export interface Tile {
  col:       number;
  row:       number;
  tile_type: string;   // e.g. "water", "road_ns", "tree_pine", "house"
  layer:     number;   // 0–3
  built_by:  string | null;
  built_day: number | null;
}

/** What an agent is currently doing — drives animation state. */
export type AgentAction = "idle" | "walking" | "building" | "talking" | "chasing" | "fleeing";

/** Which direction the agent is facing (for sprite flipping). */
export type FacingDir = "north" | "south" | "east" | "west";

/** Live agent state sent in WebSocket "state" and "agent_update" events. */
export interface Agent {
  name:          string;
  role:          string;
  tokens:        number;
  age_days:      number;
  alive:         boolean;
  mood?:         string;
  // Phase 5 position (96×72 grid — mapped to iso grid in frontend)
  x?:            number;
  y?:            number;
  // Phase 6 iso grid position (0–63)
  col?:          number;
  row?:          number;
  // Phase 6 animation state
  action?:       AgentAction;
  facing?:       FacingDir;
}

/** Construction project in progress. */
export interface ConstructionProject {
  id:           number;
  name:         string;
  tile_type:    string;
  target_col:   number;
  target_row:   number;
  stage:        number;  // 1–5
  total_stages: number;
  builders:     string[];
  started_day:  number;
}

/** A WS message event (agent dispatches). */
export interface MessageEvent {
  type:    "message";
  from:    string;
  to:      string;
  body:    string;
  day:     number;
}

/**
 * Two agents physically met (from MeetingManager).
 * Participants should walk to zone_x/zone_y on the iso map.
 */
export interface MeetingEvent {
  type:         "meeting";
  participants: string[];   // [agent_a_name, agent_b_name]
  location:     string;     // zone ID, e.g. "LOC_DARK_ALLEY"
  zone_x:       number;     // zone centre in 96×72 space (set by city_v3.py)
  zone_y:       number;
  outcome:      string;
  day:          number;
}

/** A tile_placed WS event broadcast when a tile changes. */
export interface TilePlacedEvent {
  type:     "tile_placed";
  tile:     Tile;
  day:      number;
}

/**
 * A tile_removed WS event — fired when a tile is deleted from the world
 * (e.g. a builder clears a tree before laying a road).
 */
export interface TileRemovedEvent {
  type:  "tile_removed";
  col:   number;
  row:   number;
  layer: number;
  day:   number;
}

/** Construction progress WS event. */
export interface ConstructionProgressEvent {
  type:     "construction_progress";
  project:  ConstructionProject;
  day:      number;
}

/**
 * agent_state WS event — fired after each agent acts each day.
 * Carries the agent's current position (in 96×72 space) and action type.
 * Frontend maps x/y → col/row using scaleToGrid().
 */
export interface AgentStateEvent {
  type:       "agent_state";
  name:       string;
  role:       string;
  action:     AgentAction;
  x:          number;   // position in 96×72 tile space
  y:          number;
  facing:     FacingDir;
  day:        number;
}

/** Bulk position update — sent on each time-phase transition. */
export interface PositionsEvent {
  type:   "positions";
  agents: Array<{ name: string; x: number; y: number; role: string; status: string }>;
}

/** The full state snapshot sent on WS connect / "state" event. */
export interface WorldState {
  day:              number;
  agents:           Agent[];
  vault:            number;
  events:           unknown[];
  messages:         unknown[];
  relationships:    unknown[];
  api_cost_today?:  number;
  api_cost_total?:  number;
}

/** Union of all WebSocket event types the client can receive. */
export type WSEvent =
  | { type: "state";                 data: WorldState }
  | TilePlacedEvent
  | TileRemovedEvent
  | ConstructionProgressEvent
  | AgentStateEvent
  | PositionsEvent
  | MessageEvent
  | MeetingEvent
  | { type: "time_phase";            phase: "dawn" | "morning" | "afternoon" | "dusk" | "night" }
  | { type: "death";                 agent: string; cause: string; day: number }
  | { type: "birth";                 agent: Agent }
  | { type: "construction_complete"; project: ConstructionProject; day: number }
  | { type: string;                  [key: string]: unknown };

// ── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Map a Phase 5 position (x in 0–96, y in 0–72) to the 64×64 iso grid.
 * The Phase 5 PositionManager uses a 96×72 space.
 * The Phase 6 iso world is 64×64 tiles.
 */
export function scaleToGrid(x: number, y: number): { col: number; row: number } {
  return {
    col: Math.min(63, Math.max(0, Math.round(x * 63 / 96))),
    row: Math.min(63, Math.max(0, Math.round(y * 63 / 72))),
  };
}
