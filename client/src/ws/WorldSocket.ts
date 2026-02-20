/**
 * WorldSocket.ts — WebSocket client with auto-reconnect
 *
 * Connects to the FastAPI /ws endpoint.
 * Parses incoming JSON and dispatches typed events to registered handlers.
 *
 * Why auto-reconnect?
 * The Python simulation can restart mid-run (crashes, hot-reload during dev).
 * Without reconnect logic the browser shows a dead canvas forever.
 * We retry with exponential backoff: 1s → 2s → 4s → … capped at 30s.
 */

import { WSEvent } from "@/types";

type EventHandler = (event: WSEvent) => void;

export class WorldSocket {
  private _url:      string;
  private _ws:       WebSocket | null = null;
  private _handlers: EventHandler[]   = [];
  private _retryMs   = 1000;  // start at 1 second
  private _maxRetryMs = 30_000;
  private _dead       = false; // set to true by .close()

  // ── Connection status callback (used to update the status dot in the UI) ──
  onStatusChange?: (connected: boolean) => void;

  constructor(url: string) {
    this._url = url;
    this._connect();
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /** Register a handler that receives every parsed WS event. */
  on(handler: EventHandler): void {
    this._handlers.push(handler);
  }

  /** Cleanly close the socket (no reconnect). */
  close(): void {
    this._dead = true;
    this._ws?.close();
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private _connect(): void {
    if (this._dead) return;

    this._ws = new WebSocket(this._url);

    this._ws.addEventListener("open", () => {
      console.log("[WorldSocket] connected");
      this._retryMs = 1000; // reset backoff on success
      this.onStatusChange?.(true);
    });

    this._ws.addEventListener("message", (e) => {
      try {
        const event = JSON.parse(e.data) as WSEvent;
        for (const handler of this._handlers) {
          handler(event);
        }
      } catch (err) {
        console.warn("[WorldSocket] parse error:", err, e.data);
      }
    });

    this._ws.addEventListener("close", () => {
      console.log(`[WorldSocket] disconnected — retrying in ${this._retryMs}ms`);
      this.onStatusChange?.(false);
      this._scheduleReconnect();
    });

    this._ws.addEventListener("error", () => {
      // error always precedes close, so just let close handle the retry
      this.onStatusChange?.(false);
    });
  }

  private _scheduleReconnect(): void {
    if (this._dead) return;
    setTimeout(() => this._connect(), this._retryMs);
    // Exponential backoff: double each time, cap at 30s
    this._retryMs = Math.min(this._retryMs * 2, this._maxRetryMs);
  }
}
