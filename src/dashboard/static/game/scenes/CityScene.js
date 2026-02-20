/**
 * CityScene.js — AIcity Phase 5
 * Main game scene:
 *   - Renders the 96×72 tile city map with 4 layers
 *   - Camera: panning via mouse drag, zoom via scroll wheel
 *   - WebSocket: receives all simulation events, logs to console
 *     (full visual handlers added in Sprint 3 & 4)
 *
 * Tile rendering:
 *   Each tile in the JSON is 16×16px. With game zoom=2 the game
 *   logical canvas is 960×720, and every world pixel = 2 screen pixels.
 *   The camera scrolls across the 96×16 × 72×16 = 1536×1152 world.
 */

/* global Phaser, ZONES, ROLE_CONFIG, getRoleConfig, getZoneCenter */

const TILE_SIZE      = 16;   // asset tile size (px)
const WORLD_W        = 96 * TILE_SIZE;   // 1536
const WORLD_H        = 72 * TILE_SIZE;   // 1152

class CityScene extends Phaser.Scene {
  constructor() {
    super({ key: 'CityScene' });

    // Internal state
    this.ws          = null;
    this.wsReady     = false;
    this._isDragging = false;
    this._dragStart  = { x: 0, y: 0 };
    this._camStart   = { scrollX: 0, scrollY: 0 };

    // Phase 5 Sprint 3: AgentManager handles all sprite creation + movement
    this.agentManager = null;

    // Day/Night overlay (Sprint 4)
    this.skyOverlay  = null;

    // Sprint 4: visual systems
    this.dayNight      = null;
    this.eventAnimator = null;
    this.mapManager    = null;

    // Last received time phase
    this.timePhase = 'morning';
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  create() {
    this._buildTilemap();
    this._buildCamera();
    this._buildSkyOverlay();
    this._buildZoneDebugOverlay();
    this._buildHUD();
    this._setupCameraControls();

    // Sprint 3: AgentManager — spawns and moves agent sprites
    this.agentManager = new AgentManager(this);

    // Sprint 4: visual systems (constructed after skyOverlay and agentManager exist)
    this.dayNight      = new DayNight(this);
    this.eventAnimator = new EventAnimator(this);
    this.mapManager    = new MapManager(this);

    this._setupWebSocket();

    // Launch UIScene overlay on top of this scene
    this.scene.launch('UIScene');

    console.log('[AIcity] CityScene ready. World: %dx%d px', WORLD_W, WORLD_H);
  }

  update() {
    if (this.agentManager) this.agentManager.update();
  }

  // ── Tilemap ───────────────────────────────────────────────────────────────

  _buildTilemap() {
    const map = this.make.tilemap({ key: 'citymap' });
    this.cityMap = map;

    const terrainTS   = map.addTilesetImage('terrain',   'terrain');
    const buildingTS  = map.addTilesetImage('buildings', 'buildings');
    const natureTS    = map.addTilesetImage('nature',    'nature');

    // Layer order: ground → paths → buildings → decoration
    this.groundLayer    = map.createLayer('ground',     terrainTS,  0, 0);
    this.pathLayer      = map.createLayer('paths',      terrainTS,  0, 0);
    this.buildingLayer  = map.createLayer('buildings',  buildingTS, 0, 0);
    this.decorLayer     = map.createLayer('decoration', natureTS,   0, 0);

    // Depth ordering
    this.groundLayer.setDepth(0);
    this.pathLayer.setDepth(1);
    this.buildingLayer.setDepth(2);
    this.decorLayer.setDepth(3);
    // Agent sprites will be depth 5 (Sprint 3)

    console.log('[AIcity] Tilemap loaded: %d×%d tiles', map.width, map.height);
  }

  // ── Camera ────────────────────────────────────────────────────────────────

  _buildCamera() {
    const cam = this.cameras.main;
    cam.setBounds(0, 0, WORLD_W, WORLD_H);

    // Start focused on Town Square (centre of city)
    const townCenter = getZoneCenter('LOC_TOWN_SQUARE', TILE_SIZE);
    cam.centerOn(townCenter.x, townCenter.y);
  }

  _setupCameraControls() {
    const cam = this.cameras.main;

    // Mouse drag to pan
    this.input.on('pointerdown', (ptr) => {
      this._isDragging = true;
      this._dragStart  = { x: ptr.x, y: ptr.y };
      this._camStart   = { scrollX: cam.scrollX, scrollY: cam.scrollY };
    });

    this.input.on('pointermove', (ptr) => {
      if (!this._isDragging) return;
      const dx = (ptr.x - this._dragStart.x) / this.cameras.main.zoom;
      const dy = (ptr.y - this._dragStart.y) / this.cameras.main.zoom;
      cam.setScroll(this._camStart.scrollX - dx, this._camStart.scrollY - dy);
    });

    this.input.on('pointerup', () => { this._isDragging = false; });

    // Scroll wheel zoom (clamp 0.5 – 3.0)
    this.input.on('wheel', (ptr, objs, dx, dy) => {
      const factor = dy > 0 ? 0.9 : 1.1;
      const newZoom = Phaser.Math.Clamp(cam.zoom * factor, 0.5, 3.0);
      cam.setZoom(newZoom);
    });

    // Arrow key pan (gentle drift)
    this.cursors = this.input.keyboard.createCursorKeys();
  }

  // ── Sky overlay (day/night) ───────────────────────────────────────────────

  _buildSkyOverlay() {
    // Full-screen rect that tints the world for time-of-day effect.
    // Fixed to camera so it always covers the viewport.
    this.skyOverlay = this.add.rectangle(0, 0, WORLD_W * 4, WORLD_H * 4, 0x000000, 0)
      .setDepth(50)
      .setScrollFactor(0)
      .setOrigin(0, 0);
    // Sprint 4: DayNight.js will take over this overlay.
  }

  // ── Zone debug overlay (dev-only, toggled with D key) ────────────────────

  _buildZoneDebugOverlay() {
    this._debugGraphics = this.add.graphics().setDepth(60).setVisible(false);
    this._debugVisible  = false;

    // Draw zone bounding boxes
    const colors = {
      LOC_POLICE_STATION:   0x1565C0,
      LOC_DARK_ALLEY:       0xFF3131,
      LOC_WHISPERING_CAVES: 0x7B1FA2,
      LOC_MARKET:           0xAB47BC,
      LOC_TOWN_SQUARE:      0x4CAF50,
      LOC_BUILDER_YARD:     0xFF8C00,
      LOC_CLINIC:           0xF06292,
      LOC_SCHOOL:           0xFDD835,
      LOC_VAULT:            0x78909C,
    };

    const g = this._debugGraphics;
    if (typeof ZONES !== 'undefined') {
      Object.entries(ZONES).forEach(([id, z]) => {
        const color = colors[id] || 0x888888;
        g.lineStyle(1, color, 0.6);
        g.strokeRect(
          z.x1 * TILE_SIZE, z.y1 * TILE_SIZE,
          (z.x2 - z.x1) * TILE_SIZE, (z.y2 - z.y1) * TILE_SIZE
        );
      });
    }

    this.input.keyboard.on('keydown-D', () => {
      this._debugVisible = !this._debugVisible;
      this._debugGraphics.setVisible(this._debugVisible);
      console.log('[AIcity] Zone debug overlay:', this._debugVisible ? 'ON' : 'OFF');
    });
  }

  // ── HUD overlay (day counter + phase) ────────────────────────────────────

  _buildHUD() {
    // Fixed to screen (scrollFactor 0)
    this._hudDay = this.add.text(8, 8, 'Day —', {
      fontFamily: 'Share Tech Mono, monospace',
      fontSize:   '8px',
      color:      '#00FF41',
      backgroundColor: 'rgba(0,0,0,0.55)',
      padding: { x: 6, y: 4 },
    }).setDepth(70).setScrollFactor(0);

    this._hudPhase = this.add.text(8, 26, 'Phase: morning', {
      fontFamily: 'Share Tech Mono, monospace',
      fontSize:   '8px',
      color:      '#00cc33',
      backgroundColor: 'rgba(0,0,0,0.55)',
      padding: { x: 6, y: 4 },
    }).setDepth(70).setScrollFactor(0);

    this._hudHint = this.add.text(8, 44, 'D = zones | drag = pan | scroll = zoom', {
      fontFamily: 'Share Tech Mono, monospace',
      fontSize:   '7px',
      color:      '#004400',
      backgroundColor: 'rgba(0,0,0,0.4)',
      padding: { x: 6, y: 3 },
    }).setDepth(70).setScrollFactor(0);
  }

  // ── WebSocket ─────────────────────────────────────────────────────────────

  _setupWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url   = `${proto}//${location.host}/ws`;

    const connect = () => {
      console.log('[AIcity WS] Connecting to', url);
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.wsReady = true;
        console.log('[AIcity WS] Connected');
      };

      this.ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data);
          this._handleServerEvent(event);
        } catch (err) {
          console.warn('[AIcity WS] Bad message:', e.data);
        }
      };

      this.ws.onclose = () => {
        this.wsReady = false;
        console.warn('[AIcity WS] Disconnected — reconnecting in 3s');
        setTimeout(connect, 3000);
      };

      this.ws.onerror = (err) => {
        console.error('[AIcity WS] Error:', err);
      };
    };

    connect();
  }

  // ── Event handler ─────────────────────────────────────────────────────────

  _handleServerEvent(event) {
    switch (event.type) {

      // ── State: initial snapshot on connect ──────────────────────────────
      case 'state':
        if (this._hudDay) this._hudDay.setText(`Day ${event.data?.day ?? '—'}`);
        if (this.agentManager) this.agentManager.initFromState(event.data);
        console.log('[AIcity] state — day', event.data?.day, '— agents:', event.data?.agents?.length);
        break;

      // ── Positions: agents move ───────────────────────────────────────────
      case 'positions':
        if (this.agentManager) this.agentManager.updatePositions(event.agents);
        break;

      // ── Time phase: dawn / morning / afternoon / evening / night ─────────
      case 'time_phase':
        this.timePhase = event.phase;
        if (this._hudPhase) this._hudPhase.setText(`Phase: ${event.phase}`);
        if (this.agentManager) this.agentManager.onTimePhase(event.phase);
        if (this.dayNight)     this.dayNight.setPhase(event.phase);  // Sprint 4
        console.log('[AIcity] time_phase →', event.phase);
        break;

      // ── Per-agent update ─────────────────────────────────────────────────
      case 'agent_update':
        if (this.agentManager) this.agentManager.updateAgent(event.agent);
        break;

      // ── Events with visual effects ───────────────────────────────────────
      case 'theft':
        if (this.eventAnimator) this.eventAnimator.playTheft(event);
        console.log('[AIcity] theft —', event.agent, '→', event.target);
        break;

      case 'arrest':
        if (this.eventAnimator) this.eventAnimator.playArrest(event);
        console.log('[AIcity] arrest —', event.agent, 'arrested', event.target);
        break;

      case 'death':
        if (this.eventAnimator) this.eventAnimator.playDeath(event);  // BEFORE killAgent — sprite still exists
        if (this.agentManager)  this.agentManager.killAgent(event.agent);
        console.log('[AIcity] death —', event.agent, '— cause:', event.cause);
        break;

      case 'birth':
        if (this.agentManager) this.agentManager.spawnAgent(event);
        console.log('[AIcity] birth — new agent:', event.agent, '(', event.role, ')');
        break;

      case 'asset_built':
        if (this.mapManager) this.mapManager.placeBuilding(event);
        console.log('[AIcity] asset_built —', event.project_name);
        break;

      case 'home_claimed':
        if (this.mapManager) this.mapManager.placeHome(event);
        console.log('[AIcity] home_claimed —', event.agent, 'at', event.lot_id);
        break;

      case 'meeting':
        if (this.eventAnimator) this.eventAnimator.playMeeting(event);
        console.log('[AIcity] meeting —', event.participants, 'at', event.location, '—', event.outcome);
        break;

      case 'gang_formed':
      case 'gang_event':
        if (this.eventAnimator) this.eventAnimator.playGangForm(event);
        console.log('[AIcity] gang_event —', event);
        break;

      case 'heart_attack':
        if (this.eventAnimator) this.eventAnimator.playHeartAttack(event);
        console.log('[AIcity] heart_attack —', event.agent);
        break;

      case 'newspaper':
        console.log('[AIcity] newspaper — day', event.day);
        break;

      case 'weekly_report':
      case 'monthly_chronicle':
        console.log('[AIcity]', event.type, '— week', event.week);
        break;

      case 'verdict':
        console.log('[AIcity] verdict —', event.verdict?.guilty ? 'GUILTY' : 'NOT GUILTY');
        break;

      default:
        // Uncomment to debug unknown events:
        // console.log('[AIcity] unhandled event:', event.type, event);
        break;
    }
  }

  // ── Simple phase color (Sprint 4 replaces with DayNight.js) ─────────────

  _applySimplePhaseColor(phase) {
    if (!this.skyOverlay) return;

    const configs = {
      dawn:      { color: 0xFF7B54, alpha: 0.35 },
      morning:   { color: 0x000000, alpha: 0.00 },
      afternoon: { color: 0x000000, alpha: 0.00 },
      evening:   { color: 0xFF6B35, alpha: 0.22 },
      night:     { color: 0x0D1B2A, alpha: 0.60 },
    };

    const cfg = configs[phase] || configs.morning;
    this.skyOverlay.setFillStyle(cfg.color, cfg.alpha);
  }

  // ── Public helpers (used by Sprint 3 AgentManager) ───────────────────────

  /**
   * Pan camera to a world pixel position over `duration` ms.
   * @param {number} wx — world x in pixels
   * @param {number} wy — world y in pixels
   */
  panTo(wx, wy, duration = 800) {
    this.cameras.main.pan(wx, wy, duration, 'Sine.InOut');
  }

  /**
   * Pan camera to zone center.
   * @param {string} zoneId
   */
  panToZone(zoneId, duration = 800) {
    const center = getZoneCenter(zoneId, TILE_SIZE);
    this.panTo(center.x, center.y, duration);
  }
}
