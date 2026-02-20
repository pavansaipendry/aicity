/**
 * Camera.ts — Pan and zoom controller for the isometric world
 *
 * The 64×64 tile world is ~4200×2200 px in world-space.
 * The canvas is maybe 1400×900 px.
 *
 * The Camera doesn't move — it adjusts the world container's
 * position (pan) and scale (zoom) so the right slice of the world
 * is visible on screen.
 *
 * Controls:
 *   Mouse drag  → pan (hold left button, drag)
 *   Scroll wheel → zoom in/out (centres on cursor position)
 *   Touch pinch  → zoom (mobile, future Sprint)
 */

import { Application, Container } from "pixi.js";
import { GRID_COLS, GRID_ROWS, TILE_W, TILE_H, ORIGIN_X, ORIGIN_Y } from "./IsoGrid";

const ZOOM_MIN   = 0.25;
const ZOOM_MAX   = 3.0;
const ZOOM_STEP  = 0.12; // fractional change per scroll tick

export class Camera {
  private _app:       Application;
  private _world:     Container;

  private _dragging   = false;
  private _dragStart  = { x: 0, y: 0 };
  private _panStart   = { x: 0, y: 0 };

  constructor(app: Application, worldContainer: Container) {
    this._app   = app;
    this._world = worldContainer;

    this._centerView();
    this._bindEvents();
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /** Current zoom level. */
  get zoom(): number { return this._world.scale.x; }

  /** Pan so that tile (col, row) is centred on screen. */
  centerOnTile(col: number, row: number): void {
    const wx = ORIGIN_X + (col - row) * (TILE_W / 2);
    const wy = ORIGIN_Y + (col + row) * (TILE_H / 2);
    const s  = this.zoom;
    this._world.x = this._app.screen.width  / 2 - wx * s;
    this._world.y = this._app.screen.height / 2 - wy * s;
  }

  // ── Private ────────────────────────────────────────────────────────────────

  /** Position the camera so the centre of the map is centred on screen. */
  private _centerView(): void {
    const initialZoom = 0.6; // show most of the 64×64 grid at start
    this._world.scale.set(initialZoom);

    // Centre of the isometric grid in world-space
    const midCol = GRID_COLS / 2;
    const midRow = GRID_ROWS / 2;
    this.centerOnTile(midCol, midRow);
  }

  private _bindEvents(): void {
    const canvas = this._app.canvas as HTMLCanvasElement;

    // ── Mouse drag (pan) ────────────────────────────────────────────────────
    canvas.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return; // left button only
      this._dragging  = true;
      this._dragStart = { x: e.clientX, y: e.clientY };
      this._panStart  = { x: this._world.x, y: this._world.y };
      canvas.style.cursor = "grabbing";
    });

    canvas.addEventListener("pointermove", (e) => {
      if (!this._dragging) return;
      const dx = e.clientX - this._dragStart.x;
      const dy = e.clientY - this._dragStart.y;
      this._world.x = this._panStart.x + dx;
      this._world.y = this._panStart.y + dy;
    });

    const stopDrag = () => {
      this._dragging = false;
      canvas.style.cursor = "grab";
    };
    canvas.addEventListener("pointerup",    stopDrag);
    canvas.addEventListener("pointerleave", stopDrag);

    canvas.style.cursor = "grab";

    // ── Scroll wheel (zoom) ─────────────────────────────────────────────────
    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();

      const oldZoom = this.zoom;
      const delta   = e.deltaY < 0 ? 1 + ZOOM_STEP : 1 - ZOOM_STEP;
      const newZoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, oldZoom * delta));

      if (newZoom === oldZoom) return;

      // Zoom towards the cursor position (so the point under the cursor
      // stays fixed on screen — exactly like Google Maps behaviour).
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      // The cursor's world position before zoom
      const wx = (mouseX - this._world.x) / oldZoom;
      const wy = (mouseY - this._world.y) / oldZoom;

      this._world.scale.set(newZoom);

      // Re-position so the same world point is under the cursor
      this._world.x = mouseX - wx * newZoom;
      this._world.y = mouseY - wy * newZoom;
    }, { passive: false });
  }
}
