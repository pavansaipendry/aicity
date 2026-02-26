/**
 * IsoWorld.ts — Isometric world renderer
 *
 * Owns a PixiJS Container that holds every visible tile.
 * Uses a sprite pool so tile updates are cheap (modify, don't recreate).
 *
 * Sprint 1 rendering strategy: programmatic coloured diamonds.
 * No image assets needed — just draw diamond shapes using PixiJS v8 Graphics.
 * This lets us verify the grid math immediately.
 * When Kenney sprite sheets arrive (Sprint 2), we swap _drawTile() only.
 *
 * Why sortableChildren?
 * PixiJS draws children in array order by default — first in = behind.
 * sortableChildren tells PixiJS to sort by the zIndex property before every
 * render, so we don't have to manage draw order manually.
 * depthOrder(col, row, layer) gives each tile a unique z-depth.
 *
 * Sprint 3 addition: road auto-connect.
 * When a road tile is placed, _resolveRoadType() inspects the four cardinal
 * neighbours in the pool to pick the correct visual variant:
 *   road_ns   — connects north+south (or dead-end)
 *   road_ew   — connects east+west
 *   road_cross — 3 or 4 connections
 *   road_corner — one N/S and one E/W connection
 * After placing, _updateNeighbourRoads() redraws adjacent road tiles so they
 * also re-evaluate their connections.
 */

import { Application, Container, Graphics } from "pixi.js";
import { Tile } from "@/types";
import { tileToWorld, depthOrder, TILE_W, TILE_H } from "./IsoGrid";

// ── Tile colour palette (programmatic, pre-Kenney) ─────────────────────────
const TILE_COLOURS: Record<string, number> = {
  // Ground layer (layer 0)
  grass:       0x4a7c59,
  water:       0x3a7bd5,
  dirt:        0x8b6914,
  sand:        0xd4b896,

  // Road layer (layer 1) — warm sandy tan, clearly contrasts against grass
  road_ns:     0xC8A86E,
  road_ew:     0xC8A86E,
  road_cross:  0xD4B87A,   // slightly brighter at intersections
  road_corner: 0xC8A86E,
  road:        0xC8A86E,   // generic fallback before resolution

  // Nature layer (layer 2)
  tree_pine:   0x2d6a2d,
  tree_oak:    0x3a7a3a,
  bush:        0x4a8c4a,
  rock:        0x888888,

  // Building layer (layer 3)
  house:           0xc4713a,
  house_small:     0xc4713a,
  market:          0xd4843a,
  hospital:        0xffffff,
  school:          0xd4c43a,
  police_station:  0x4169E1,
  warehouse:       0x8b7d6b,
  archive:         0x8b6914,
  barracks:        0x556655,

  // Special tiles
  gravestone:  0x666666,

  // Construction stages
  construction_1: 0x8b6914,
  construction_2: 0x9b7924,
  construction_3: 0xab8934,
  construction_4: 0xbb9944,
  construction_5: 0xcba954,
};

const DEFAULT_COLOUR = 0x4a7c59; // fallback = grass

/** Height above the base diamond — taller tiles look "taller" in 3D. */
const TILE_EXTRUDE: Record<string, number> = {
  tree_pine:   18,
  tree_oak:    14,
  rock:        6,
  bush:        4,
  house:           20,
  house_small:     16,
  market:          22,
  hospital:        28,
  school:          24,
  police_station:  22,
  warehouse:       18,
  archive:         26,
  barracks:        18,
  gravestone:      8,
};
const DEFAULT_EXTRUDE = 0;


export class IsoWorld {
  /** The PixiJS container — add this to the stage. */
  readonly container: Container;

  /** Sprite pool: key = "col,row,layer", value = Graphics object. */
  private _pool: Map<string, Graphics> = new Map();

  /**
   * Tile data store: key = "col,row,layer", value = original Tile.
   * Needed so neighbour road tiles can be redrawn when a new road is placed.
   */
  private _tileData: Map<string, Tile> = new Map();

  constructor(_app: Application) {
    this.container = new Container();
    this.container.sortableChildren = true;

    // Draw the base grass plane immediately so the grid is visible
    this._drawGrassPlane();
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Render a tile (or update it if it already exists in the pool).
   * Called for every tile from /api/world on load, and for each tile_placed event.
   *
   * Sprint 3: road tiles trigger auto-connect after drawing.
   */
  setTile(tile: Tile): void {
    const key = `${tile.col},${tile.row},${tile.layer}`;
    let gfx = this._pool.get(key);

    if (!gfx) {
      gfx = new Graphics();
      this.container.addChild(gfx);
      this._pool.set(key, gfx);
    }

    // Store tile data for neighbour lookups
    this._tileData.set(key, tile);

    gfx.clear();
    this._drawTile(gfx, tile);
    gfx.zIndex = depthOrder(tile.col, tile.row, tile.layer);

    // Road auto-connect: redraw neighbours so they update their variant too
    if (tile.tile_type.startsWith("road") || tile.tile_type === "road") {
      this._updateNeighbourRoads(tile.col, tile.row);
    }
  }

  /**
   * Remove a tile from the renderer (tile reverts to grass).
   */
  removeTile(col: number, row: number, layer: number): void {
    const key = `${col},${row},${layer}`;
    const gfx = this._pool.get(key);
    if (gfx) {
      this.container.removeChild(gfx);
      gfx.destroy();
      this._pool.delete(key);
      this._tileData.delete(key);
    }
  }

  /**
   * Replace the entire world with a fresh tile list.
   * Called once on startup after /api/world returns.
   *
   * Sprint 3: after all tiles are loaded we do a second pass over every road
   * tile to resolve auto-connect correctly (first-pass order can't see future
   * neighbours yet).
   */
  loadWorld(tiles: Tile[]): void {
    // Clear existing non-grass pool entries
    for (const [, gfx] of this._pool) {
      this.container.removeChild(gfx);
      gfx.destroy();
    }
    this._pool.clear();
    this._tileData.clear();

    // Re-draw grass base
    this._drawGrassPlane();

    // Paint all tiles from backend (roads stored with placeholder type)
    for (const tile of tiles) {
      this.setTile(tile);
    }

    // Second pass: re-render every road tile now that all neighbours exist
    for (const [key, tile] of this._tileData) {
      if (tile.tile_type.startsWith("road") || tile.tile_type === "road") {
        const gfx = this._pool.get(key);
        if (gfx) {
          gfx.clear();
          this._drawTile(gfx, tile);
        }
      }
    }
  }

  // ── Private rendering ──────────────────────────────────────────────────────

  /**
   * Draw a single diamond-shaped tile using PixiJS v8 Graphics.
   *
   * An isometric diamond has 4 corners:
   *   top:    (0,        0)
   *   right:  (TILE_W/2, TILE_H/2)
   *   bottom: (0,        TILE_H)
   *   left:  (-TILE_W/2, TILE_H/2)
   *
   * For tiles with height (buildings, trees) we also draw the left and right
   * "faces" to give a 3D box effect.
   *
   * Sprint 3: road tiles have their type resolved via _resolveRoadType() so
   * road_cross appears slightly brighter than road_ns/road_ew/road_corner.
   */
  private _drawTile(gfx: Graphics, tile: Tile): void {
    const { x, y } = tileToWorld(tile.col, tile.row);

    // Road tiles: resolve the correct variant based on live neighbours
    const resolvedType = (tile.tile_type.startsWith("road") || tile.tile_type === "road")
      ? this._resolveRoadType(tile.col, tile.row)
      : tile.tile_type;

    const colour  = TILE_COLOURS[resolvedType] ?? DEFAULT_COLOUR;
    const extrude = TILE_EXTRUDE[resolvedType] ?? DEFAULT_EXTRUDE;

    const hw = TILE_W / 2;
    const hh = TILE_H / 2;

    if (extrude > 0) {
      // ── Left face (darker shade) ───────────────────────────────────────
      const leftFace = darken(colour, 0.55);
      gfx.poly([
        x - hw,  y + hh,             // bottom-left of top diamond
        x,       y + TILE_H,         // bottom point of top diamond
        x,       y + TILE_H - extrude, // bottom point raised
        x - hw,  y + hh  - extrude,  // back up
      ]).fill(leftFace);

      // ── Right face (medium shade) ──────────────────────────────────────
      const rightFace = darken(colour, 0.7);
      gfx.poly([
        x,       y + TILE_H,
        x + hw,  y + hh,
        x + hw,  y + hh  - extrude,
        x,       y + TILE_H - extrude,
      ]).fill(rightFace);
    }

    // ── Top diamond face (full colour) ────────────────────────────────────
    gfx.poly([
      x,       y - extrude,           // top
      x + hw,  y + hh - extrude,      // right
      x,       y + TILE_H - extrude,  // bottom
      x - hw,  y + hh - extrude,      // left
    ]).fill(colour);
  }

  /**
   * Draw a 64×64 grass plane as a single batched Graphics call.
   * This is the "background" — all non-grass tiles are painted on top.
   * Pooled under the key "grass_plane" so it can be reused.
   */
  private _drawGrassPlane(): void {
    const existing = this._pool.get("grass_plane");
    if (existing) return;

    const gfx = new Graphics();
    gfx.zIndex = -1; // always behind everything

    const colour = TILE_COLOURS["grass"];
    const hw = TILE_W / 2;
    const hh = TILE_H / 2;

    // Draw every grass tile in a single Graphics call — much cheaper than
    // 4096 separate Graphics objects.
    for (let col = 0; col < 64; col++) {
      for (let row = 0; row < 64; row++) {
        const { x, y } = tileToWorld(col, row);
        // Alternate slightly so individual tiles are distinguishable
        const c = ((col + row) % 2 === 0) ? colour : darken(colour, 0.93);
        gfx.poly([x, y, x + hw, y + hh, x, y + TILE_H, x - hw, y + hh]).fill(c);
      }
    }

    this.container.addChild(gfx);
    this._pool.set("grass_plane", gfx);
  }

  // ── Sprint 3: road auto-connect ────────────────────────────────────────────

  /**
   * Inspect the four cardinal neighbours in the pool to pick the correct
   * road visual variant for tile at (col, row).
   *
   * Neighbours are on layer 1 (road layer).  A road tile is present when
   * the pool contains that key (regardless of specific road variant).
   *
   * Variant selection table:
   *   4 connections → road_cross
   *   3 connections → road_cross   (T-junction, same colour for now)
   *   N + S only    → road_ns
   *   E + W only    → road_ew
   *   any corner    → road_corner
   *   dead-end/solo → road_ns
   */
  private _resolveRoadType(col: number, row: number): string {
    const hasRoad = (c: number, r: number): boolean =>
      this._pool.has(`${c},${r},1`);

    const n = hasRoad(col,     row - 1);
    const s = hasRoad(col,     row + 1);
    const e = hasRoad(col + 1, row    );
    const w = hasRoad(col - 1, row    );
    const count = [n, s, e, w].filter(Boolean).length;

    if (count >= 3)        return "road_cross";
    if (n && s)            return "road_ns";
    if (e && w)            return "road_ew";
    if ((n || s) && (e || w)) return "road_corner";
    return "road_ns";  // dead-end or isolated
  }

  /**
   * After placing a new road tile, re-draw adjacent road tiles so their
   * auto-connect variant updates to include the new connection.
   */
  private _updateNeighbourRoads(col: number, row: number): void {
    const offsets: [number, number][] = [[0, -1], [0, 1], [1, 0], [-1, 0]];
    for (const [dc, dr] of offsets) {
      const nc  = col + dc;
      const nr  = row + dr;
      const key = `${nc},${nr},1`;
      const tileData = this._tileData.get(key);
      const gfx      = this._pool.get(key);
      if (tileData && gfx) {
        gfx.clear();
        this._drawTile(gfx, tileData);
      }
    }
  }
}


// ── Helpers ────────────────────────────────────────────────────────────────

/**
 * Darken a hex colour by a factor (0 = black, 1 = original).
 * Used for side-face shading to create the 3D box illusion.
 */
function darken(colour: number, factor: number): number {
  const r = Math.floor(((colour >> 16) & 0xff) * factor);
  const g = Math.floor(((colour >>  8) & 0xff) * factor);
  const b = Math.floor(((colour >>  0) & 0xff) * factor);
  return (r << 16) | (g << 8) | b;
}
