/**
 * SpeechBubble.ts — Conversation bubbles above agents' heads
 *
 * Sprint 5 responsibility:
 *   - Shows a white rounded-rect bubble above the sender when a "message"
 *     event arrives.
 *   - Bubble displays a short excerpt of the message body (max 40 chars).
 *   - Fades out over 4 seconds, then self-destructs.
 *   - Multiple bubbles can exist simultaneously (one per recent message).
 *
 * Design:
 *   ┌──────────────────────────┐
 *   │ "Let's build a market!" │
 *   └────────────┬─────────────┘
 *                ▼
 *           [agent pawn]
 */

import { Application, Container, Graphics, Text, TextStyle } from "pixi.js";
import { tileToWorld, depthOrder } from "@/engine/IsoGrid";

// ── Configuration ─────────────────────────────────────────────────────────────
const BUBBLE_LIFE_MS  = 4000;    // total lifetime before removal
const FADE_START_MS   = 2500;    // start fading after this many ms
const MAX_TEXT_LEN    = 40;      // truncate message body beyond this
const BUBBLE_PAD_X    = 8;       // horizontal padding inside bubble
const BUBBLE_PAD_Y    = 5;       // vertical padding
const BUBBLE_Y_OFFSET = -50;     // above agent pawn (higher = further up)
const TAIL_SIZE       = 5;       // speech bubble tail triangle size
const MAX_BUBBLES     = 8;       // limit concurrent bubbles for performance

interface BubbleEntry {
  container: Container;
  startTime: number;
}

export class SpeechBubbleSystem {
  private _stage:   Container;
  private _bubbles: BubbleEntry[] = [];

  constructor(app: Application, worldContainer: Container) {
    this._stage = worldContainer;

    // Tick every frame to handle fade + cleanup
    app.ticker.add(() => this._onTick());
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Show a speech bubble above a tile position.
   * @param col - iso grid column of the speaker
   * @param row - iso grid row of the speaker
   * @param body - the message text
   */
  show(col: number, row: number, body: string): void {
    // Enforce max concurrent bubbles — remove oldest if at limit
    while (this._bubbles.length >= MAX_BUBBLES) {
      const oldest = this._bubbles.shift()!;
      this._removeBubble(oldest);
    }

    const text = body.length > MAX_TEXT_LEN
      ? body.slice(0, MAX_TEXT_LEN - 1) + "…"
      : body;

    const container = new Container();
    const { x, y } = tileToWorld(col, row);
    container.x = x;
    container.y = y + BUBBLE_Y_OFFSET;
    container.zIndex = depthOrder(col, row, 5);   // layer 5 = above everything

    // Text first (to measure width)
    const style = new TextStyle({
      fontFamily: "Share Tech Mono, monospace",
      fontSize:   10,
      fill:       0x111111,
      wordWrap:   true,
      wordWrapWidth: 180,
    });
    const label = new Text({ text, style });
    label.anchor.set(0.5, 0.5);

    // Background bubble
    const bw = label.width + BUBBLE_PAD_X * 2;
    const bh = label.height + BUBBLE_PAD_Y * 2;
    const gfx = new Graphics();

    // Rounded rect body
    gfx.roundRect(-bw / 2, -bh / 2, bw, bh, 6)
       .fill({ color: 0xffffff, alpha: 0.92 });
    gfx.roundRect(-bw / 2, -bh / 2, bw, bh, 6)
       .stroke({ width: 1, color: 0x444444, alpha: 0.5 });

    // Tail triangle pointing down
    gfx.poly([
      -TAIL_SIZE, bh / 2,
       TAIL_SIZE, bh / 2,
       0,         bh / 2 + TAIL_SIZE,
    ]).fill({ color: 0xffffff, alpha: 0.92 });

    container.addChild(gfx);
    container.addChild(label);
    this._stage.addChild(container);

    this._bubbles.push({
      container,
      startTime: performance.now(),
    });
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private _onTick(): void {
    const now = performance.now();
    const toRemove: number[] = [];

    for (let i = 0; i < this._bubbles.length; i++) {
      const b   = this._bubbles[i];
      const age = now - b.startTime;

      if (age >= BUBBLE_LIFE_MS) {
        toRemove.push(i);
        continue;
      }

      // Fade phase
      if (age >= FADE_START_MS) {
        const fadeProgress = (age - FADE_START_MS) / (BUBBLE_LIFE_MS - FADE_START_MS);
        b.container.alpha = 1 - fadeProgress;
      }
    }

    // Remove expired bubbles (iterate backwards to keep indices valid)
    for (let i = toRemove.length - 1; i >= 0; i--) {
      const idx   = toRemove[i];
      const entry = this._bubbles[idx];
      this._removeBubble(entry);
      this._bubbles.splice(idx, 1);
    }
  }

  private _removeBubble(entry: BubbleEntry): void {
    this._stage.removeChild(entry.container);
    entry.container.destroy({ children: true });
  }
}
