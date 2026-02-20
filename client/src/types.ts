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

/** Live agent state sent in WebSocket "state" and "agent_update" events. */
export interface Agent {
  name:          string;
  role:          string;
  tokens:        number;
  age_days:      number;
  alive:         boolean;
  mood?:         string;
  col?:          number;  // current tile position (Phase 6 adds this)
  row?:          number;
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

/** A tile_placed WS event broadcast when a tile changes. */
export interface TilePlacedEvent {
  type:     "tile_placed";
  tile:     Tile;
  day:      number;
}

/** Construction progress WS event. */
export interface ConstructionProgressEvent {
  type:     "construction_progress";
  project:  ConstructionProject;
  day:      number;
}

/** The full state snapshot sent on WS connect / "state" event. */
export interface WorldState {
  day:           number;
  agents:        Agent[];
  vault:         number;
  events:        unknown[];
  messages:      unknown[];
  relationships: unknown[];
}

/** Union of all WebSocket event types the client can receive. */
export type WSEvent =
  | { type: "state";                data: WorldState }
  | TilePlacedEvent
  | ConstructionProgressEvent
  | MessageEvent
  | { type: "positions";            agents: Array<{ name: string; col: number; row: number }> }
  | { type: "time_phase";           phase: "dawn" | "morning" | "afternoon" | "dusk" | "night" }
  | { type: "death";                agent: string; cause: string; day: number }
  | { type: "birth";                agent: Agent }
  | { type: "construction_complete"; project: ConstructionProject; day: number }
  | { type: string;                 [key: string]: unknown };
