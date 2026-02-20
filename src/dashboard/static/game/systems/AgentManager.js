/**
 * systems/AgentManager.js — AIcity Phase 5 Sprint 3
 *
 * Manages all agent sprites on the city canvas.
 * Uses placeholder 8×8 tinted squares until real LPC sprite sheets arrive.
 *
 * Each agent entry: { sprite, nameLabel, roleLabel, tokenBarBg, tokenBar, data, patrolStep }
 *
 * Coordinate system:
 *   Tile (tx, ty) → world pixel (tx * TILE_PX, ty * TILE_PX)
 *   Game zoom=2 makes each 16-world-px tile render as 32 screen pixels.
 */

/* global Phaser, ZONES, getRoleConfig, getZoneCenter */

const TILE_PX = 16;           // world pixels per tile (matches CityScene TILE_SIZE)
const TOKEN_BAR_W  = 12;      // max width of the token health bar in world px
const TOKEN_FULL   = 2000;    // tokens at which bar is considered "full"

// Police patrol waypoints in tile coords — matches Python PATROL_WAYPOINTS
const PATROL_WPS = [
  { x: 61, y: 35 },   // station exit
  { x: 18, y: 38 },   // market district
  { x: 73, y: 63 },   // dark alley
  { x: 40, y: 30 },   // town square
  { x: 61, y: 35 },   // back to station
];

class AgentManager {
  constructor(scene) {
    this.scene = scene;

    // name → { sprite, nameLabel, roleLabel, tokenBarBg, tokenBar, data, patrolStep }
    this.agents = new Map();

    // True while time_phase is morning or afternoon — police patrol runs
    this._patrolActive = false;
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Called once on the initial 'state' event.
   * Spawns sprites for every alive agent.
   */
  initFromState(stateData) {
    if (!stateData || !Array.isArray(stateData.agents)) return;
    stateData.agents.forEach(a => {
      if (a.status === 'alive') this.spawnAgent(a);
    });
    console.log(`[AgentManager] initFromState — ${this.agents.size} agents spawned.`);
  }

  /**
   * Spawn (or refresh) a single agent sprite.
   * Safe to call multiple times; re-uses existing entry if name already exists.
   */
  spawnAgent(agentData) {
    const { name, role, x = 40, y = 30, tokens = 1000, status = 'alive' } = agentData;

    if (status === 'dead') return;

    if (this.agents.has(name)) {
      this.updateAgent(agentData);
      return;
    }

    const cfg = getRoleConfig(role);
    const wx = (x || 40) * TILE_PX;
    const wy = (y || 30) * TILE_PX;

    // ── Placeholder sprite: tinted 16×16 circle texture ──────────────────
    const sprite = this.scene.add.image(wx, wy, 'agent_placeholder')
      .setDepth(5)
      .setTint(cfg.tint)
      .setScale(1.5);   // 16 → 24 world-px circle; 48 screen-px at game zoom=2

    // ── Name label (First + Last-initial to avoid duplicate first names) ───
    const parts = name.split(' ');
    const firstName = parts.length > 1
      ? `${parts[0]} ${parts[1][0]}.`
      : parts[0];
    const nameLabel = this.scene.add.text(wx, wy - 22, firstName, {
      fontFamily: 'Share Tech Mono, monospace',
      fontSize:   '9px',
      color:      '#ffffff',
      stroke:     '#000000',
      strokeThickness: 3,
      backgroundColor: 'rgba(0,0,0,0.65)',
      padding:    { x: 3, y: 2 },
    }).setDepth(7).setOrigin(0.5, 1);

    // ── Role badge (3-char abbreviation, tinted) ──────────────────────────
    const hexColor = `#${cfg.tint.toString(16).padStart(6, '0')}`;
    const roleLabel = this.scene.add.text(wx, wy - 13, cfg.label, {
      fontFamily: 'Share Tech Mono, monospace',
      fontSize:   '7px',
      color:      hexColor,
      stroke:     '#000000',
      strokeThickness: 2,
    }).setDepth(7).setOrigin(0.5, 1);

    // ── Token health bar (below sprite) ───────────────────────────────────
    const tokenBarBg = this.scene.add.rectangle(wx, wy + 14, TOKEN_BAR_W, 3, 0x111111)
      .setDepth(5).setOrigin(0.5, 0);

    const tokenBar = this.scene.add.rectangle(
      wx - TOKEN_BAR_W / 2, wy + 14, TOKEN_BAR_W, 3, 0x00FF41
    ).setDepth(6).setOrigin(0, 0);

    this.agents.set(name, {
      sprite,
      nameLabel,
      roleLabel,
      tokenBarBg,
      tokenBar,
      data:       { ...agentData },
      patrolStep: 0,
    });

    this._updateTokenBar(name, tokens);

    console.log(`[AgentManager] Spawned: ${name} (${role}) at tile (${(x||40).toFixed(1)}, ${(y||30).toFixed(1)})`);
  }

  /**
   * Update an existing agent's token bar and cached data.
   * Called on 'agent_update' events.
   */
  updateAgent(agentData) {
    if (!agentData?.name) return;
    const { name, tokens, status } = agentData;

    const entry = this.agents.get(name);
    if (!entry) {
      // Not yet on canvas — spawn if alive
      if (status === 'alive') this.spawnAgent(agentData);
      return;
    }

    // Merge new data
    entry.data = { ...entry.data, ...agentData };

    // Update token bar
    if (tokens !== undefined) this._updateTokenBar(name, tokens);

    // If the server says dead, fade out
    if (status === 'dead') this.killAgent(name);
  }

  /**
   * Receive a positions bulk update and move all agents.
   * Called on 'positions' WebSocket events.
   * Police agents are skipped while patrol is active (patrol loop owns their movement).
   */
  updatePositions(positionArray) {
    if (!Array.isArray(positionArray)) return;
    positionArray.forEach(pos => {
      if (!pos.name) return;
      if (pos.status === 'dead') return;

      const entry = this.agents.get(pos.name);

      // Police stays on patrol route during morning/afternoon
      if (entry?.data.role === 'police' && this._patrolActive) return;

      this.moveTo(pos.name, pos.x, pos.y);
    });
  }

  /**
   * React to a time_phase change.
   * Starts police patrol on morning/afternoon; stops on evening/night.
   */
  onTimePhase(phase) {
    if (phase === 'morning' || phase === 'afternoon') {
      if (!this._patrolActive) {
        this._patrolActive = true;
        // Kick off patrol for every police agent currently on the canvas
        this.agents.forEach((entry, name) => {
          if (entry.data.role === 'police') {
            entry.patrolStep = 0;  // restart from station
            this._tickPatrol(name);
          }
        });
        console.log('[AgentManager] Police patrol started.');
      }
    } else {
      if (this._patrolActive) {
        this._patrolActive = false;
        console.log('[AgentManager] Police patrol stopped (phase:', phase, ')');
      }
    }
  }

  /**
   * Tween-based movement to a tile position.
   * Kills any existing movement tween on the sprite before starting a new one.
   *
   * @param {string} name     — agent name
   * @param {number} targetX  — destination tile x
   * @param {number} targetY  — destination tile y
   * @param {Function} [onComplete] — callback when tween finishes
   */
  moveTo(name, targetX, targetY, onComplete) {
    const entry = this.agents.get(name);
    if (!entry) return;

    const { sprite, nameLabel, roleLabel, tokenBarBg, tokenBar } = entry;

    const tx = (targetX || 0) * TILE_PX;
    const ty = (targetY || 0) * TILE_PX;

    const dx = tx - sprite.x;
    const dy = ty - sprite.y;
    const dist = Math.sqrt(dx * dx + dy * dy);

    // Already there — skip
    if (dist < 2) {
      if (onComplete) onComplete();
      return;
    }

    // Stop any existing tween on this sprite before starting a new one
    this.scene.tweens.killTweensOf(sprite);

    const duration = Math.max(500, dist * 35);  // ~35ms per world px of distance

    this.scene.tweens.add({
      targets:  sprite,
      x:        tx,
      y:        ty,
      duration,
      ease:     'Linear',
      onUpdate: () => {
        // Keep all UI elements anchored to sprite position
        const sx = sprite.x;
        const sy = sprite.y;
        nameLabel.setPosition(sx, sy - 22);
        roleLabel.setPosition(sx, sy - 13);
        tokenBarBg.setPosition(sx, sy + 14);
        tokenBar.setPosition(sx - TOKEN_BAR_W / 2, sy + 14);
      },
      onComplete: () => {
        // Snap UI to final position
        nameLabel.setPosition(tx, ty - 22);
        roleLabel.setPosition(tx, ty - 13);
        tokenBarBg.setPosition(tx, ty + 14);
        tokenBar.setPosition(tx - TOKEN_BAR_W / 2, ty + 14);
        if (onComplete) onComplete();
      },
    });
  }

  /**
   * Fade out and destroy a dead agent's visual elements.
   * Called on 'death' events (Sprint 4 EventAnimator adds more drama).
   */
  killAgent(name) {
    const entry = this.agents.get(name);
    if (!entry) return;

    const targets = [
      entry.sprite,
      entry.nameLabel,
      entry.roleLabel,
      entry.tokenBarBg,
      entry.tokenBar,
    ];

    // Stop movement
    this.scene.tweens.killTweensOf(entry.sprite);

    this.scene.tweens.add({
      targets,
      alpha:    0,
      duration: 2000,
      ease:     'Sine.In',
      onComplete: () => {
        targets.forEach(t => t.destroy());
        this.agents.delete(name);
        console.log(`[AgentManager] ${name} removed from canvas.`);
      },
    });
  }

  /**
   * Called from CityScene.update() every frame.
   * Stub for future per-frame logic (Sprint 4+).
   */
  update() {
    // All movement is tween-driven — no per-frame logic needed yet.
  }

  // ── Internal ───────────────────────────────────────────────────────────────

  /**
   * Update the token health bar width and color.
   * Green > 400 | Yellow 200–400 | Red < 200
   */
  _updateTokenBar(name, tokens) {
    const entry = this.agents.get(name);
    if (!entry) return;

    const t = tokens ?? 0;
    const ratio = Math.min(1, Math.max(0, t / TOKEN_FULL));
    const w = Math.max(1, TOKEN_BAR_W * ratio);
    entry.tokenBar.width = w;

    const color = t > 400 ? 0x00FF41 : t > 200 ? 0xFFD700 : 0xFF3131;
    entry.tokenBar.setFillStyle(color);
  }

  /**
   * Move police agent to the next patrol waypoint.
   * Recursively called after each waypoint is reached, while _patrolActive.
   */
  _tickPatrol(name) {
    const entry = this.agents.get(name);
    if (!entry || !this._patrolActive) return;

    const wp = PATROL_WPS[entry.patrolStep % PATROL_WPS.length];
    entry.patrolStep++;

    this.moveTo(name, wp.x, wp.y, () => {
      // Short pause at waypoint, then move on
      this.scene.time.delayedCall(800, () => {
        if (this._patrolActive && this.agents.has(name)) {
          this._tickPatrol(name);
        }
      });
    });
  }
}
