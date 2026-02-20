/**
 * BootScene.js — AIcity Phase 5
 * Preloads all game assets and shows a progress bar.
 * Transitions to CityScene when everything is loaded.
 */

class BootScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BootScene' });
  }

  preload() {
    // ── Progress bar UI ────────────────────────────────────────────────────
    const { width, height } = this.cameras.main;
    const cx = width / 2;
    const cy = height / 2;

    const barBg = this.add.rectangle(cx, cy, 300, 20, 0x003d10).setOrigin(0.5);
    const bar   = this.add.rectangle(cx - 150, cy, 0, 16, 0x00FF41).setOrigin(0, 0.5);

    const loadText = this.add.text(cx, cy - 30, 'LOADING AICITY...', {
      fontFamily: 'Share Tech Mono, monospace',
      fontSize:   '12px',
      color:      '#00cc33',
    }).setOrigin(0.5);

    const percentText = this.add.text(cx, cy + 20, '0%', {
      fontFamily: 'Share Tech Mono, monospace',
      fontSize:   '10px',
      color:      '#008822',
    }).setOrigin(0.5);

    this.load.on('progress', (value) => {
      bar.width = 296 * value;
      percentText.setText(Math.floor(value * 100) + '%');
    });

    this.load.on('complete', () => {
      loadText.setText('CITY READY');
      percentText.setText('100%');
    });

    // ── Tilemap ────────────────────────────────────────────────────────────
    this.load.tilemapTiledJSON('citymap', '/static/game/data/citymap.json');

    // ── Tilesets ───────────────────────────────────────────────────────────
    this.load.image('terrain',   '/static/game/assets/tilesets/terrain.png');
    this.load.image('buildings', '/static/game/assets/tilesets/buildings.png');
    this.load.image('nature',    '/static/game/assets/tilesets/nature.png');

    // ── Placeholder agent sprite ───────────────────────────────────────────
    // 16×16 circle — tinted per role in AgentManager (Sprint 3)
    const agentCanvas = this.textures.createCanvas('agent_placeholder', 16, 16);
    const ctx = agentCanvas.getContext();
    ctx.clearRect(0, 0, 16, 16);
    // Filled circle
    ctx.beginPath();
    ctx.arc(8, 8, 7, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    // Dark outline for contrast over any tile colour
    ctx.strokeStyle = 'rgba(0,0,0,0.55)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    agentCanvas.refresh();
  }

  create() {
    this.scene.start('CityScene');
  }
}
