/**
 * systems/DayNight.js — AIcity Phase 5 Sprint 4
 *
 * Takes over the sky overlay from CityScene._applySimplePhaseColor().
 * Adds smooth alpha/color tweens per time phase and street lamp glow circles.
 *
 * Design:
 *   - skyOverlay: full-screen rectangle (created in CityScene._buildSkyOverlay)
 *     DayNight owns it from construction onward.
 *   - Lamps: small ADD-blend circles placed at street intersections.
 *     Alpha tweens: visible at evening/night, hidden at day.
 *
 * Coordinate system: tile coords × TILE_PX = world pixels.
 * TILE_PX is declared in AgentManager.js (loaded before this file).
 */

/* global Phaser, TILE_PX */

// Street lamp positions in tile coordinates
const LAMP_TILES = [
  // Main Street (y = 36)
  { x: 28, y: 36 }, { x: 40, y: 36 }, { x: 54, y: 36 },
  // Town Square (y ≈ 30)
  { x: 34, y: 30 }, { x: 40, y: 30 }, { x: 46, y: 30 },
  // Elm Street (y = 25)
  { x: 26, y: 25 }, { x: 48, y: 25 },
  // South Road (y = 50)
  { x: 32, y: 50 }, { x: 46, y: 50 },
  // Dark Alley entrance (dim red lamp)
  { x: 65, y: 60 },
];

class DayNight {
  /**
   * @param {Phaser.Scene} scene — CityScene instance.
   *   Must be constructed after _buildSkyOverlay() runs so scene.skyOverlay exists.
   */
  constructor(scene) {
    this.scene      = scene;
    this.skyOverlay = scene.skyOverlay;
    this.lamps      = [];

    this._phases = {
      dawn:      { alpha: 0.35, color: 0xFF7B54, lampAlpha: 0.55 },
      morning:   { alpha: 0.00, color: 0x000000, lampAlpha: 0.00 },
      afternoon: { alpha: 0.00, color: 0x000000, lampAlpha: 0.00 },
      evening:   { alpha: 0.28, color: 0xFF6B35, lampAlpha: 0.45 },
      night:     { alpha: 0.65, color: 0x0D1B2A, lampAlpha: 1.00 },
    };

    // Reset skyOverlay — DayNight owns alpha control from here.
    // fillAlpha=1 so we only need to tween the game-object alpha.
    this.skyOverlay.setFillStyle(0x000000, 1);
    this.skyOverlay.setAlpha(0);

    this._placeLamps();
    console.log(`[DayNight] Ready — ${this.lamps.length / 2} lamp positions.`);
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Smoothly transition to a new time phase.
   * Changes sky color (instant — invisible while alpha tweens) then tweens alpha.
   * @param {string} phase — dawn | morning | afternoon | evening | night
   */
  setPhase(phase) {
    const cfg = this._phases[phase] || this._phases.morning;

    // Sky: change fill color instantly (safe — color hidden while alpha is low),
    // then smoothly tween game-object alpha.
    this.scene.tweens.killTweensOf(this.skyOverlay);
    this.skyOverlay.setFillStyle(cfg.color, 1);
    this.scene.tweens.add({
      targets:  this.skyOverlay,
      alpha:    cfg.alpha,
      duration: 2500,
      ease:     'Sine.InOut',
    });

    // Street lamps: fade in or out
    this.lamps.forEach(lamp => {
      this.scene.tweens.killTweensOf(lamp);
      this.scene.tweens.add({
        targets:  lamp,
        alpha:    cfg.lampAlpha,
        duration: 1800,
        ease:     'Sine.InOut',
      });
    });
  }

  // ── Internal ───────────────────────────────────────────────────────────────

  /**
   * Place two-layer glow circles at each lamp position.
   * Both layers start at alpha=0 (invisible during daytime).
   * Outer: large soft halo   Inner: tight bright core
   */
  _placeLamps() {
    LAMP_TILES.forEach(({ x, y }) => {
      const wx = x * TILE_PX;
      const wy = y * TILE_PX;

      // Outer soft halo
      const outer = this.scene.add.circle(wx, wy, 24, 0xFFE87C, 0)
        .setDepth(48)
        .setBlendMode(Phaser.BlendModes.ADD);

      // Inner bright core
      const inner = this.scene.add.circle(wx, wy, 7, 0xFFFACD, 0)
        .setDepth(49)
        .setBlendMode(Phaser.BlendModes.ADD);

      this.lamps.push(outer, inner);
    });
  }
}
