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

  // Road layer (layer 1)
  road_ns:     0x555566,
  road_ew:     0x555566,
  road_cross:  0x666677,
  road_corner: 0x555566,

  // Nature layer (layer 2)
  tree_pine:   0x2d6a2d,
  tree_oak:    0x3a7a3a,
  bush:        0x4a8c4a,
  rock:        0x888888,

  // Building layer (layer 3)
  house:       0xc4713a,
  market:      0xd4843a,
  hospital:    0xffffff,
  school:      0xd4c43a,
  archive:     0x8b6914,
  barracks:    0x556655,

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
  house:       20,
  market:      22,
  hospital:    28,
  school:      24,
  archive:     26,
  barracks:    18,
};
const DEFAULT_EXTRUDE = 0;


export class IsoWorld {
  /** The PixiJS container — add this to the stage. */
  readonly container: Container;

  /** Sprite pool: key = "col,row,layer", value = Graphics object. */
  private _pool: Map<string, Graphics> = new Map();

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
   */
  setTile(tile: Tile): void {
    const key = `${tile.col},${tile.row},${tile.layer}`;
    let gfx = this._pool.get(key);

    if (!gfx) {
      gfx = new Graphics();
      this.container.addChild(gfx);
      this._pool.set(key, gfx);
    }

    gfx.clear();
    this._drawTile(gfx, tile);
    gfx.zIndex = depthOrder(tile.col, tile.row, tile.layer);
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
    }
  }

  /**
   * Replace the entire world with a fresh tile list.
   * Called once on startup after /api/world returns.
   */
  loadWorld(tiles: Tile[]): void {
    // Clear existing non-grass pool entries
    for (const [, gfx] of this._pool) {
      this.container.removeChild(gfx);
      gfx.destroy();
    }
    this._pool.clear();

    // Re-draw grass base
    this._drawGrassPlane();

    // Paint all tiles from backend
    for (const tile of tiles) {
      this.setTile(tile);
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
   */
  private _drawTile(gfx: Graphics, tile: Tile): void {
    const { x, y } = tileToWorld(tile.col, tile.row);
    const colour   = TILE_COLOURS[tile.tile_type] ?? DEFAULT_COLOUR;
    const extrude  = TILE_EXTRUDE[tile.tile_type] ?? DEFAULT_EXTRUDE;

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
