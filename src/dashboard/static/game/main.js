/**
 * game/main.js — AIcity Phase 5
 * Phaser 3 entry point. Loaded after Phaser CDN script tag.
 *
 * Config:
 *   - 960×720 logical canvas, zoom×2 so each 16px tile renders at 32px on screen
 *   - pixelArt: true  → crisp no-antialiasing rendering
 *   - Scenes: BootScene → CityScene → UIScene (UIScene overlaid)
 */

/* global Phaser, BootScene, CityScene, UIScene */

const GAME_CONFIG = {
  type: Phaser.AUTO,
  width: 960,
  height: 720,
  parent: 'game-canvas',
  backgroundColor: '#1a1a2e',
  pixelArt: true,
  zoom: 2,
  physics: {
    default: 'arcade',
    arcade: { debug: false },
  },
  scene: [BootScene, CityScene],
  // UIScene added in Sprint 3 when sprites are live
};

// Boot the game only when the City tab is first clicked (called from app.js).
// Do NOT auto-boot on page load — Phaser needs a visible container with real dimensions.
function bootGame() {
  const container = document.getElementById('game-canvas');
  if (!container) {
    console.warn('[AIcity] #game-canvas not found — game not booted');
    return;
  }
  if (window.AICITY_GAME) {
    return; // Already booted — guard against double-call
  }
  window.AICITY_GAME = new Phaser.Game(GAME_CONFIG);
  console.log('[AIcity] Phaser game booted.');
}
