/**
 * EventHandler.ts — Routes WebSocket events to the correct systems
 *
 * This is the wiring layer between the network (WorldSocket) and the
 * renderer (IsoWorld).  Every event type gets a dedicated handler here.
 *
 * Adding a new event type later:
 *   1. Add it to WSEvent union in types.ts
 *   2. Add a case in _dispatch() below
 *   3. Write the handler method
 *
 * Why separate from WorldSocket?
 * WorldSocket handles reconnects, framing, JSON parsing.
 * EventHandler handles game logic.  Swap the transport without touching game.
 */

import { WSEvent, TilePlacedEvent, ConstructionProgressEvent } from "@/types";
import { IsoWorld } from "@/engine/IsoWorld";

/** Callback signatures for UI updates outside the canvas. */
export interface UICallbacks {
  /** Called when a "state" snapshot arrives — updates agent list, vault, etc. */
  onState?: (data: WSEvent & { type: "state" }) => void;
  /** Called when connection status changes. */
  onStatus?: (connected: boolean) => void;
  /** Called when a "death" event arrives. */
  onDeath?: (agentName: string, cause: string, day: number) => void;
  /** Called when a "construction_complete" event arrives. */
  onBuildComplete?: (projectName: string, day: number) => void;
}

export class EventHandler {
  private _world:     IsoWorld;
  private _callbacks: UICallbacks;

  constructor(world: IsoWorld, callbacks: UICallbacks = {}) {
    this._world     = world;
    this._callbacks = callbacks;
  }

  /**
   * Handle one parsed WS event.  Called by WorldSocket on every message.
   */
  handle(event: WSEvent): void {
    switch (event.type) {
      case "state":
        this._onState(event as WSEvent & { type: "state" });
        break;

      case "tile_placed":
        this._onTilePlaced(event as TilePlacedEvent);
        break;

      case "construction_progress":
        this._onConstructionProgress(event as ConstructionProgressEvent);
        break;

      case "construction_complete":
        this._onConstructionComplete(event as WSEvent & { type: "construction_complete" });
        break;

      case "death":
        this._onDeath(event as WSEvent & { type: "death" });
        break;

      // Ignore high-frequency events that don't affect the tile world
      case "positions":
      case "time_phase":
      case "agent_update":
        break;

      default:
        // Unknown event — log in dev, ignore in prod
        if ((import.meta as { env?: { DEV?: boolean } }).env?.DEV) {
          console.debug("[EventHandler] unhandled event:", event.type);
        }
    }
  }

  // ── Handlers ───────────────────────────────────────────────────────────────

  private _onState(event: WSEvent & { type: "state" }): void {
    // The state snapshot doesn't contain tile data (that's loaded via /api/world).
    // Forward to UI layer for agent list, vault, etc.
    this._callbacks.onState?.(event);
  }

  private _onTilePlaced(event: TilePlacedEvent): void {
    // A single tile changed — update just that tile in the renderer.
    this._world.setTile(event.tile);
  }

  private _onConstructionProgress(event: ConstructionProgressEvent): void {
    const { project } = event;
    // Render a construction stage tile at the project site
    this._world.setTile({
      col:       project.target_col,
      row:       project.target_row,
      tile_type: `construction_${project.stage}`,
      layer:     3,
      built_by:  project.builders[0] ?? null,
      built_day: event.day,
    });
  }

  private _onConstructionComplete(event: WSEvent & { type: "construction_complete" }): void {
    const project = (event as unknown as ConstructionProgressEvent).project;
    if (project) {
      // Replace construction tile with the finished building
      this._world.setTile({
        col:       project.target_col,
        row:       project.target_row,
        tile_type: project.tile_type,
        layer:     3,
        built_by:  project.builders[0] ?? null,
        built_day: event.day as number,
      });
    }
    this._callbacks.onBuildComplete?.(
      project?.name ?? "building",
      event.day as number
    );
  }

  private _onDeath(event: WSEvent & { type: "death" }): void {
    const e = event as { type: "death"; agent: string; cause: string; day: number };
    this._callbacks.onDeath?.(e.agent, e.cause, e.day);
  }
}
