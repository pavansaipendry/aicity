/**
 * AgentTooltip.ts — Click-to-inspect tooltip for agents
 *
 * Sprint 6: clicking an agent pawn shows a small card with:
 *   - Name + role
 *   - Tokens balance
 *   - Mood
 *   - Current action
 *
 * The tooltip is rendered in screen-space (overlay) so it doesn't
 * pan/zoom with the world. It auto-hides after 5 seconds or on
 * clicking elsewhere.
 */

import { Application, Container, Graphics, Text, TextStyle } from "pixi.js";

const TOOLTIP_W       = 180;
const TOOLTIP_PAD     = 10;
const TOOLTIP_LIFE_MS = 5000;
const CORNER_R        = 6;

interface AgentInfo {
  name:    string;
  role:    string;
  tokens?: number;
  mood?:   string;
  action?: string;
}

export class AgentTooltip {
  private _overlay: Container;
  private _current: Container | null = null;
  private _timer:   ReturnType<typeof setTimeout> | null = null;

  constructor(app: Application) {
    // Overlay container sits on top of everything (screen-space)
    this._overlay = new Container();
    this._overlay.zIndex = 9999;
    app.stage.addChild(this._overlay);

    // Click anywhere on stage to dismiss
    app.stage.eventMode = "static";
    app.stage.on("pointerdown", () => this.hide());
  }

  show(screenX: number, screenY: number, info: AgentInfo): void {
    this.hide();

    const container = new Container();

    // Build text lines
    const lines = [
      `${info.name}`,
      `Role: ${info.role}`,
    ];
    if (info.tokens !== undefined) lines.push(`Tokens: ${info.tokens}`);
    if (info.mood)                 lines.push(`Mood: ${info.mood}`);
    if (info.action)               lines.push(`Action: ${info.action}`);

    const bodyText = lines.join("\n");

    const nameStyle = new TextStyle({
      fontFamily: "Share Tech Mono, monospace",
      fontSize:   11,
      fontWeight: "bold",
      fill:       0xffffff,
      wordWrap:   true,
      wordWrapWidth: TOOLTIP_W - TOOLTIP_PAD * 2,
    });

    const label = new Text({ text: bodyText, style: nameStyle });
    label.x = TOOLTIP_PAD;
    label.y = TOOLTIP_PAD;

    const h = label.height + TOOLTIP_PAD * 2;

    // Background
    const bg = new Graphics();
    bg.roundRect(0, 0, TOOLTIP_W, h, CORNER_R)
      .fill({ color: 0x1a1a2e, alpha: 0.92 });
    bg.roundRect(0, 0, TOOLTIP_W, h, CORNER_R)
      .stroke({ width: 1, color: 0x00ff41, alpha: 0.6 });

    container.addChild(bg);
    container.addChild(label);

    // Position: offset so tooltip doesn't go off-screen
    container.x = Math.min(screenX + 10, window.innerWidth - TOOLTIP_W - 10);
    container.y = Math.max(screenY - h - 10, 10);

    this._overlay.addChild(container);
    this._current = container;

    // Auto-hide
    this._timer = setTimeout(() => this.hide(), TOOLTIP_LIFE_MS);
  }

  hide(): void {
    if (this._current) {
      this._overlay.removeChild(this._current);
      this._current.destroy({ children: true });
      this._current = null;
    }
    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }
  }
}
