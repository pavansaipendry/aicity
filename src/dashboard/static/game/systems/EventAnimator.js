/**
 * systems/EventAnimator.js — AIcity Phase 5 Sprint 4
 *
 * Visual animations for simulation events received over WebSocket.
 *
 *  playTheft(event)       — gold particles burst from victim, victim flashes red
 *  playArrest(event)      — police moves to criminal, criminal turns grey
 *  playDeath(event)       — gravestone placed, red pulse (call BEFORE killAgent)
 *  playMeeting(event)     — teal glow ring at zone center, outcome text
 *  playHeartAttack(event) — double red pulse rings, healer rushes over
 *  playGangForm(event)    — orange glow at Dark Alley
 *  floatingText(...)      — shared rising-text helper used by all handlers
 *
 * All effects use built-in Phaser graphics and tweens — no external texture files needed.
 * TILE_PX and getZoneCenter are globals from AgentManager.js and zones.js.
 */

/* global Phaser, TILE_PX, getZoneCenter */

class EventAnimator {
  /**
   * @param {Phaser.Scene} scene — CityScene instance
   */
  constructor(scene) {
    this.scene = scene;
    console.log('[EventAnimator] Ready.');
  }

  // ── Public event handlers ──────────────────────────────────────────────────

  /**
   * Theft: victim flashes red, gold token particles burst outward, floating loss text.
   * event: { agent: thief_name, target: victim_name, tokens?: number }
   */
  playTheft(event) {
    const victim = this._getEntry(event.target);
    if (!victim) return;

    const vx = victim.sprite.x;
    const vy = victim.sprite.y;

    // Flash victim red for 600 ms
    victim.sprite.setTint(0xFF3131);
    this.scene.time.delayedCall(600, () => victim.sprite.clearTint());

    // Gold token particles burst outward
    this._tokenParticles(vx, vy);

    // Floating loss text
    const amount = event.tokens ?? event.amount ?? '?';
    this.floatingText(vx, vy - 10, `-${amount}`, '#FF3131');

    console.log(`[EventAnimator] Theft: ${event.agent} stole from ${event.target}`);
  }

  /**
   * Arrest: police sprite walks to criminal, criminal turns grey, "ARRESTED" text.
   * event: { agent: police_name, target: criminal_name }
   */
  playArrest(event) {
    const criminal = this._getEntry(event.target);
    if (!criminal) return;

    const tx = criminal.sprite.x / TILE_PX;
    const ty = criminal.sprite.y / TILE_PX;

    // Police runs to criminal
    this.scene.agentManager.moveTo(event.agent, tx, ty, () => {
      // Criminal sprite goes grey
      criminal.sprite.setTint(0x888888);
      if (criminal.nameLabel) criminal.nameLabel.setAlpha(0.5);
      // ARRESTED banner
      this.floatingText(criminal.sprite.x, criminal.sprite.y - 18, 'ARRESTED', '#FF3131');
    });

    console.log(`[EventAnimator] Arrest: ${event.agent} arrested ${event.target}`);
  }

  /**
   * Death: red pulse + gravestone placed at agent's last position.
   * IMPORTANT: call this BEFORE agentManager.killAgent() so the sprite still exists.
   * event: { agent: name, cause: string }
   */
  playDeath(event) {
    const entry = this._getEntry(event.agent);
    if (!entry) return;

    const dx = entry.sprite.x;
    const dy = entry.sprite.y;

    // Red expanding pulse
    this._pulse(dx, dy, 0xFF3131, 16);

    // Permanent gravestone marker
    this._placeGravestone(dx, dy, event.agent);

    // Cause of death text floats up
    const cause = event.cause ? `[${event.cause}]` : '[deceased]';
    this.floatingText(dx, dy - 16, cause, '#888888');

    console.log(`[EventAnimator] Death: ${event.agent} — ${event.cause}`);
  }

  /**
   * Meeting: expanding teal glow ring at zone center + outcome text.
   * event: { participants: [name, name], location: 'LOC_*', outcome: string }
   */
  playMeeting(event) {
    // Only use LOC_* zone IDs — fall back to Town Square
    const zoneId = (event.location && event.location.startsWith('LOC_'))
      ? event.location
      : 'LOC_TOWN_SQUARE';
    const center = getZoneCenter(zoneId, TILE_PX);

    // Expanding teal ring
    const glow = this.scene.add.circle(center.x, center.y, 12, 0x00FFCC, 0.45)
      .setDepth(15);
    this.scene.tweens.add({
      targets:  glow,
      scaleX:   4.5,
      scaleY:   4.5,
      alpha:    0,
      duration: 2200,
      ease:     'Sine.Out',
      onComplete: () => glow.destroy(),
    });

    // Outcome text (capped at 28 chars to fit screen)
    if (event.outcome) {
      const short = String(event.outcome).slice(0, 28);
      this.floatingText(center.x, center.y - 22, short, '#00FFCC');
    }

    console.log(`[EventAnimator] Meeting at ${zoneId}:`, event.participants);
  }

  /**
   * Heart attack: two red pulse rings + warning text + healer rushes over.
   * event: { agent: name }
   */
  playHeartAttack(event) {
    const entry = this._getEntry(event.agent);
    if (!entry) return;

    const hx = entry.sprite.x;
    const hy = entry.sprite.y;

    // Two pulses slightly offset in time
    this._pulse(hx, hy, 0xFF3131, 14);
    this.scene.time.delayedCall(380, () => this._pulse(hx, hy, 0xFF3131, 9));

    this.floatingText(hx, hy - 16, '! Heart Attack', '#FF3131');

    // Find the healer and rush them to the victim
    let healerName = null;
    this.scene.agentManager.agents.forEach((e, name) => {
      if (e.data.role === 'healer' && !healerName) healerName = name;
    });
    if (healerName && healerName !== event.agent) {
      const tx = hx / TILE_PX;
      const ty = hy / TILE_PX;
      this.scene.agentManager.moveTo(healerName, tx, ty);
    }

    console.log(`[EventAnimator] Heart attack: ${event.agent}`);
  }

  /**
   * Gang formed/event: orange glow at Dark Alley + gang name text.
   * event: { gang?: { name: string }, leader?: string }
   */
  playGangForm(event) {
    const center = getZoneCenter('LOC_DARK_ALLEY', TILE_PX);

    const glow = this.scene.add.circle(center.x, center.y, 16, 0xFF6600, 0.5)
      .setDepth(15);
    this.scene.tweens.add({
      targets:  glow,
      scaleX:   5,
      scaleY:   5,
      alpha:    0,
      duration: 2500,
      ease:     'Sine.Out',
      onComplete: () => glow.destroy(),
    });

    const gangName = event.gang?.name || 'A gang';
    this.floatingText(center.x, center.y - 26, `${gangName} formed`, '#FF6600');

    console.log(`[EventAnimator] Gang formed:`, event);
  }

  /**
   * Shared floating text helper.
   * Text rises and fades over ~1.8 seconds. Destroys itself on complete.
   *
   * @param {number} x      — world pixel x
   * @param {number} y      — world pixel y (text rises upward from here)
   * @param {string} text
   * @param {string} color  — CSS hex color string, e.g. '#FF3131'
   */
  floatingText(x, y, text, color = '#ffffff') {
    const t = this.scene.add.text(x, y, text, {
      fontFamily: 'Share Tech Mono, monospace',
      fontSize:   '7px',
      color,
      stroke:          '#000000',
      strokeThickness: 2,
    }).setDepth(30).setOrigin(0.5, 1);

    this.scene.tweens.add({
      targets:  t,
      y:        y - 30,
      alpha:    0,
      duration: 1800,
      ease:     'Cubic.Out',
      onComplete: () => t.destroy(),
    });
  }

  // ── Private helpers ────────────────────────────────────────────────────────

  /** Retrieve the agent entry from AgentManager, or null. */
  _getEntry(name) {
    if (!this.scene.agentManager) return null;
    return this.scene.agentManager.agents.get(name) ?? null;
  }

  /**
   * 8 gold dots burst outward from (x, y), staggered by 55 ms each.
   */
  _tokenParticles(x, y) {
    for (let i = 0; i < 8; i++) {
      const angle = (i / 8) * Math.PI * 2;
      const dist  = Phaser.Math.Between(18, 46);
      const dot   = this.scene.add.circle(x, y, 2.5, 0xFFD700)
        .setDepth(20)
        .setAlpha(1);

      this.scene.tweens.add({
        targets:  dot,
        x:        x + Math.cos(angle) * dist,
        y:        y + Math.sin(angle) * dist,
        alpha:    0,
        duration: Phaser.Math.Between(500, 900),
        ease:     'Cubic.Out',
        delay:    i * 55,
        onComplete: () => dot.destroy(),
      });
    }
  }

  /**
   * Single expanding circle pulse at (x, y).
   * @param {number} color — Phaser hex int
   * @param {number} size  — starting radius in world pixels
   */
  _pulse(x, y, color, size = 12) {
    const circle = this.scene.add.circle(x, y, size, color, 0.80)
      .setDepth(20);
    this.scene.tweens.add({
      targets:  circle,
      scaleX:   4.5,
      scaleY:   4.5,
      alpha:    0,
      duration: 750,
      ease:     'Cubic.Out',
      onComplete: () => circle.destroy(),
    });
  }

  /**
   * Permanent gravestone graphic at world position (wx, wy).
   * Persists on map — depth 4 (below agents at depth 5).
   */
  _placeGravestone(wx, wy, agentName) {
    // Stone body
    this.scene.add.rectangle(wx, wy + 2, 7, 10, 0x777777, 0.92)
      .setDepth(4);

    // Cross bar
    this.scene.add.rectangle(wx, wy - 2, 5, 1.5, 0x555555)
      .setDepth(4);

    // Agent initial
    this.scene.add.text(wx, wy - 14, agentName[0].toUpperCase(), {
      fontFamily: 'Share Tech Mono, monospace',
      fontSize:   '4px',
      color:      '#aaaaaa',
    }).setDepth(4).setOrigin(0.5);
  }
}
