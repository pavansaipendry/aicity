/**
 * systems/MapManager.js — AIcity Phase 5 Sprint 4
 *
 * Handles permanent map changes triggered by simulation events:
 *
 *  placeBuilding(event) — 'asset_built'
 *    Construction dust animation, then a colored footprint rectangle
 *    with building name. Placeholder until real tile art is available.
 *
 *  placeHome(event)     — 'home_claimed'
 *    Small house graphic (body + roof + owner name) at the claimed lot.
 *
 * Building specs match the lot positions defined in the plan (§3) and
 * backend home_manager.py HOME_LOTS.
 *
 * TILE_PX is a global from AgentManager.js (loaded before this file).
 */

/* global Phaser, TILE_PX */

// Building specs keyed by project_type (fuzzy-matched against event fields).
// x, y = top-left tile coord of the footprint.
// w, h = width/height in tiles.
const BUILDING_SPECS = {
  market_stall: { x: 10, y: 33, w: 6,  h: 4, color: 0xAB47BC, label: 'Market'     },
  hospital:     { x:  9, y: 45, w: 8,  h: 6, color: 0xF06292, label: 'Hospital'   },
  school:       { x: 63, y: 45, w: 10, h: 6, color: 0xFDD835, label: 'School'     },
  watchtower:   { x: 56, y: 29, w: 4,  h: 6, color: 0x1565C0, label: 'Watchtower' },
  archive:      { x:  9, y: 59, w: 8,  h: 6, color: 0x78909C, label: 'Archive'    },
  road:         { x: 16, y: 24, w: 34, h: 1, color: 0x8B8682, label: 'Road'       },
};

class MapManager {
  /**
   * @param {Phaser.Scene} scene — CityScene instance
   */
  constructor(scene) {
    this.scene   = scene;
    // Tracks placed buildings by label so we don't place the same one twice
    this._placed = new Set();
    console.log('[MapManager] Ready.');
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Triggered by 'asset_built' WebSocket event.
   * event: { project_name: string, project_type?: string }
   */
  placeBuilding(event) {
    const spec = this._findSpec(event.project_type || event.project_name || '');
    if (!spec) {
      console.log('[MapManager] No spec for:', event.project_name);
      return;
    }

    const key = spec.label;
    if (this._placed.has(key)) return;   // already on map

    const cx = (spec.x + spec.w / 2) * TILE_PX;
    const cy = (spec.y + spec.h / 2) * TILE_PX;

    // 1. Construction dust at footprint center
    this._constructionDust(cx, cy);

    // 2. After dust settles, reveal building footprint
    this.scene.time.delayedCall(1500, () => {
      const wx = spec.x * TILE_PX;
      const wy = spec.y * TILE_PX;
      const ww = spec.w * TILE_PX;
      const wh = spec.h * TILE_PX;

      // Colored semi-transparent footprint rectangle
      this.scene.add.rectangle(wx + ww / 2, wy + wh / 2, ww, wh, spec.color, 0.55)
        .setDepth(2.5)
        .setStrokeStyle(1, spec.color, 0.9);

      // Building name centered on footprint
      this.scene.add.text(cx, cy, spec.label, {
        fontFamily: 'Share Tech Mono, monospace',
        fontSize:   '6px',
        color:      '#ffffff',
        stroke:          '#000000',
        strokeThickness: 2,
      }).setDepth(3).setOrigin(0.5);

      this._placed.add(key);
      console.log(`[MapManager] ${spec.label} placed at tile (${spec.x}, ${spec.y}).`);
    });
  }

  /**
   * Triggered by 'home_claimed' WebSocket event.
   * event: { agent: string, role: string, lot_id: string, x: number, y: number }
   */
  placeHome(event) {
    if (event.x === undefined || event.y === undefined) return;

    const wx = event.x * TILE_PX;
    const wy = event.y * TILE_PX;

    // House body (warm beige rectangle)
    this.scene.add.rectangle(wx, wy + 2, 10, 8, 0xD4A96A, 0.88)
      .setDepth(2.5);

    // Roof (red triangle drawn via Graphics)
    const g = this.scene.add.graphics().setDepth(2.5);
    g.fillStyle(0xC0392B, 0.9);
    g.fillTriangle(
      wx - 7, wy - 1,   // bottom-left
      wx + 7, wy - 1,   // bottom-right
      wx,     wy - 8    // apex
    );

    // Owner first name above house
    const firstName = String(event.agent || '').split(' ')[0];
    this.scene.add.text(wx, wy - 12, firstName, {
      fontFamily: 'Share Tech Mono, monospace',
      fontSize:   '5px',
      color:      '#FFE87C',
      stroke:          '#000000',
      strokeThickness: 2,
    }).setDepth(3).setOrigin(0.5);

    console.log(`[MapManager] Home for ${event.agent} placed at tile (${event.x}, ${event.y}).`);
  }

  // ── Internal ───────────────────────────────────────────────────────────────

  /**
   * Fuzzy-match a project name/type string to a BUILDING_SPECS entry.
   * Tries exact key, then partial substring match.
   */
  _findSpec(query) {
    if (!query) return null;
    const q = query.toLowerCase();

    // 1. Exact key
    if (BUILDING_SPECS[q]) return BUILDING_SPECS[q];

    // 2. Partial match on key or label
    for (const [key, spec] of Object.entries(BUILDING_SPECS)) {
      if (q.includes(key) || key.includes(q) || q.includes(spec.label.toLowerCase())) {
        return spec;
      }
    }
    return null;
  }

  /**
   * 6 grey dust circles expand outward from (cx, cy) and fade.
   */
  _constructionDust(cx, cy) {
    for (let i = 0; i < 6; i++) {
      const angle  = (i / 6) * Math.PI * 2;
      const dist   = Phaser.Math.Between(12, 30);
      const circle = this.scene.add.circle(cx, cy, 3, 0xBBBBBB, 0.80)
        .setDepth(20);

      this.scene.tweens.add({
        targets:  circle,
        x:        cx + Math.cos(angle) * dist,
        y:        cy + Math.sin(angle) * dist,
        alpha:    0,
        duration: Phaser.Math.Between(600, 1000),
        ease:     'Cubic.Out',
        delay:    i * 80,
        onComplete: () => circle.destroy(),
      });
    }
  }
}
