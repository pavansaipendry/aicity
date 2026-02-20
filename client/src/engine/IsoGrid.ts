/**
 * IsoGrid.ts — Isometric grid math
 *
 * This file is pure math — no PixiJS, no DOM, no side effects.
 * Every other system imports from here when it needs tile↔world conversion.
 *
 * ──────────────────────────────────────────────────────────────
 * Isometric projection: what is it?
 * ──────────────────────────────────────────────────────────────
 * Normal top-down grids draw tiles in rows like a chessboard.
 * Isometric grids rotate 45° and tilt forward so you can see
 * the "side" of tiles — giving the 2.5D SimCity effect.
 *
 * The math:
 *   screenX = (col - row) * (TILE_W / 2)
 *   screenY = (col + row) * (TILE_H / 2)
 *
 * Kenney isometric tiles are 64×32 pixels (2:1 ratio — standard for iso).
 * TILE_W = 64, TILE_H = 32.
 *
 * Depth sorting:
 *   Tiles at higher (col + row) are drawn last (on top).
 *   A building at (10, 10) depth=20 covers a tree at (9, 10) depth=19.
 * ──────────────────────────────────────────────────────────────
 */

/** Width of one isometric tile in pixels (the diamond's widest point). */
export const TILE_W = 64;

/** Height of one isometric tile in pixels (the diamond's tallest point). */
export const TILE_H = 32;

/** Grid dimensions (64×64 for Sprint 1, scales to 128×128 later). */
export const GRID_COLS = 64;
export const GRID_ROWS = 64;

/** Pixel offset so the top-left tile renders near the canvas centre. */
export const ORIGIN_X = (GRID_COLS * TILE_W) / 2;
export const ORIGIN_Y = TILE_H * 2;


// ── Conversions ─────────────────────────────────────────────────────────────

/**
 * Convert a tile coordinate (col, row) to a world-space pixel position.
 * This is the position of the tile's top-centre diamond point.
 *
 * @param col  Grid column (0 = left edge)
 * @param row  Grid row    (0 = top edge)
 * @returns    { x, y } in world pixels
 */
export function tileToWorld(col: number, row: number): { x: number; y: number } {
  return {
    x: ORIGIN_X + (col - row) * (TILE_W / 2),
    y: ORIGIN_Y + (col + row) * (TILE_H / 2),
  };
}

/**
 * Convert a world-space pixel position back to the nearest tile coordinate.
 * Used for mouse-click hit-testing: "which tile did the user click?"
 *
 * Derived by inverting the tileToWorld equations:
 *   col = (x/TILE_W + y/TILE_H) / 2
 *   row = (y/TILE_H - x/TILE_W) / 2
 *
 * @param wx  World pixel X
 * @param wy  World pixel Y
 * @returns   { col, row } — may be outside grid bounds, caller should clamp
 */
export function worldToTile(wx: number, wy: number): { col: number; row: number } {
  const nx = (wx - ORIGIN_X) / (TILE_W / 2);
  const ny = (wy - ORIGIN_Y) / (TILE_H / 2);
  return {
    col: Math.floor((nx + ny) / 2),
    row: Math.floor((ny - nx) / 2),
  };
}

/**
 * Return the depth sort value for a tile.
 * Higher = drawn later = appears in front.
 *
 * Layer is added so buildings always appear in front of roads at the same tile.
 *
 * @param col    Tile column
 * @param row    Tile row
 * @param layer  Tile layer (0–3)
 */
export function depthOrder(col: number, row: number, layer: number): number {
  return (col + row) * 10 + layer;
}

/**
 * Check if (col, row) is within the valid grid bounds.
 */
export function inBounds(col: number, row: number): boolean {
  return col >= 0 && col < GRID_COLS && row >= 0 && row < GRID_ROWS;
}

/**
 * Return the four orthogonal neighbours of a tile (up/down/left/right).
 * Filters out-of-bounds positions automatically.
 */
export function neighbours(col: number, row: number): Array<{ col: number; row: number }> {
  return [
    { col: col - 1, row },
    { col: col + 1, row },
    { col, row: row - 1 },
    { col, row: row + 1 },
  ].filter(({ col: c, row: r }) => inBounds(c, r));
}
