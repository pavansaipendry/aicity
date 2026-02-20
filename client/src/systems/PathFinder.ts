/**
 * PathFinder.ts — A* pathfinding on the 64×64 isometric grid
 *
 * Wraps EasyStar.js so the rest of the codebase doesn't need to know
 * how pathfinding works internally.
 *
 * Why A* instead of straight-line movement?
 * Agents can't walk through water or trees — they need to route around them.
 * A* finds the shortest walkable path.  Without it, agents would clip through
 * the river and forest.
 *
 * Walkability rules:
 *   Grass (implicit) → walkable
 *   Road             → walkable
 *   Water            → NOT walkable
 *   Trees / rocks    → NOT walkable
 *   Buildings        → NOT walkable
 */

import EasyStar from "easystarjs";
import { Tile } from "@/types";
import { GRID_COLS, GRID_ROWS } from "@/engine/IsoGrid";

const WALKABLE   = 0;   // EasyStar value for passable
const BLOCKED    = 1;   // EasyStar value for impassable

// Tile types that block movement
const BLOCKED_TILES = new Set([
  "water",
  "tree_pine", "tree_oak", "bush", "rock",
  "house", "market", "hospital", "school", "archive", "barracks",
  "construction_1", "construction_2", "construction_3",
  "construction_4", "construction_5",
]);

export type Path = Array<{ x: number; y: number }>; // EasyStar returns {x,y}

export class PathFinder {
  private _easystar: EasyStar.js;
  private _grid: number[][];      // [row][col] = WALKABLE | BLOCKED
  private _dirty = false;

  constructor() {
    this._easystar = new EasyStar.js();
    this._grid = this._makeEmptyGrid();
    this._applyGrid();

    // Allow diagonal movement for more natural paths
    this._easystar.enableDiagonals();
    this._easystar.disableCornerCutting();

    // Run continuously in the browser (needed for async pathfinding)
    this._startTicker();
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Update walkability from the world tile list.
   * Call this once after /api/world loads, and again after each tile_placed event.
   */
  setTiles(tiles: Tile[]): void {
    // Reset to all walkable
    this._grid = this._makeEmptyGrid();

    for (const tile of tiles) {
      if (tile.col < 0 || tile.col >= GRID_COLS) continue;
      if (tile.row < 0 || tile.row >= GRID_ROWS) continue;

      if (BLOCKED_TILES.has(tile.tile_type)) {
        this._grid[tile.row][tile.col] = BLOCKED;
      }
    }

    this._applyGrid();
    this._dirty = false;
  }

  /**
   * Mark a single tile as blocked or walkable (after tile_placed event).
   */
  updateTile(tile: Tile): void {
    if (tile.col < 0 || tile.col >= GRID_COLS) return;
    if (tile.row < 0 || tile.row >= GRID_ROWS) return;

    const val = BLOCKED_TILES.has(tile.tile_type) ? BLOCKED : WALKABLE;
    this._grid[tile.row][tile.col] = val;
    this._dirty = true;
    // Re-apply lazily on next findPath call
  }

  /**
   * Find the shortest walkable path from (fromCol, fromRow) to (toCol, toRow).
   * Calls `callback` with the path array (or null if no path exists).
   *
   * EasyStar is async — it processes a fixed number of iterations per tick.
   * The callback fires on the next available tick after the path is found.
   */
  findPath(
    fromCol: number, fromRow: number,
    toCol:   number, toRow:   number,
    callback: (path: Array<[number, number]> | null) => void
  ): void {
    if (this._dirty) {
      this._applyGrid();
      this._dirty = false;
    }

    // Clamp to grid bounds
    const fc = Math.min(GRID_COLS - 1, Math.max(0, fromCol));
    const fr = Math.min(GRID_ROWS - 1, Math.max(0, fromRow));
    const tc = Math.min(GRID_COLS - 1, Math.max(0, toCol));
    const tr = Math.min(GRID_ROWS - 1, Math.max(0, toRow));

    // Same tile — no movement needed
    if (fc === tc && fr === tr) {
      callback([]);
      return;
    }

    this._easystar.findPath(fc, fr, tc, tr, (path) => {
      if (!path) {
        callback(null);
        return;
      }
      // EasyStar returns [{x: col, y: row}, ...] — convert to [col, row] tuples
      callback(path.map((p) => [p.x, p.y]));
    });
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private _makeEmptyGrid(): number[][] {
    return Array.from({ length: GRID_ROWS }, () =>
      new Array<number>(GRID_COLS).fill(WALKABLE)
    );
  }

  private _applyGrid(): void {
    this._easystar.setGrid(this._grid);
    this._easystar.setAcceptableTiles([WALKABLE]);
  }

  /**
   * EasyStar needs .calculate() called every frame to process path requests.
   * We hook into requestAnimationFrame so it runs automatically.
   */
  private _startTicker(): void {
    const tick = () => {
      this._easystar.calculate();
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
}
