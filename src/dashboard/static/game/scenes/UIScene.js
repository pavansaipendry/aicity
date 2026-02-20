/**
 * UIScene.js — AIcity Phase 5 Sprint 3
 *
 * Overlay scene that sits on top of CityScene (depth-independent, camera-fixed).
 * Currently a scaffold — Sprint 4+ will add:
 *   - Click-to-select agent info panel (name, role, mood, memories)
 *   - City infrastructure status overlay
 *   - Active criminal investigation ticker
 *
 * Runs in parallel with CityScene via Phaser's multi-scene stack.
 * All UI here is scrollFactor(0) — fixed to the viewport regardless of camera pan.
 */

class UIScene extends Phaser.Scene {
  constructor() {
    super({ key: 'UIScene', active: false });
  }

  create() {
    // UIScene is launched by CityScene once agents are live.
    // Sprint 4 will populate this scene with interactive overlays.
    console.log('[UIScene] Overlay scene active. Awaiting Sprint 4 content.');
  }

  update() {
    // Per-frame overlay updates — Sprint 4+
  }
}
