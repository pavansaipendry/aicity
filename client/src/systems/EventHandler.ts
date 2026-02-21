/**
 * EventHandler.ts — Routes WebSocket events to the correct systems
 *
 * Wiring layer between WorldSocket (network) and game systems (rendering).
 * Each event type has one handler method. Adding a new event:
 *   1. Add it to WSEvent union in types.ts
 *   2. Add a case in handle() below
 *   3. Write the handler method
 *
 * Sprint 3 addition: PathFinder is now injected so that tile_placed events
 * update the walkability grid in real time — agents route around new roads
 * and trees immediately after they're placed.
 *
 * Sprint 4 addition: ConstructionManager is injected.
 * construction_progress → ConstructionManager.onProgress()  (progress bar + builder walk)
 * construction_complete → ConstructionManager.onComplete()  (tear down progress bar)
 * Both handlers also update IsoWorld + PathFinder for the final tile.
 */

import {
  WSEvent, TilePlacedEvent, TileRemovedEvent, ConstructionProgressEvent,
  AgentStateEvent, PositionsEvent, MessageEvent, MeetingEvent, Agent,
  scaleToGrid,
} from "@/types";
import { IsoWorld }              from "@/engine/IsoWorld";
import { CharacterManager }      from "./CharacterManager";
import { PathFinder }            from "./PathFinder";
import { ConstructionManager }   from "./ConstructionManager";

export interface UICallbacks {
  onState?:         (data: WSEvent & { type: "state" }) => void;
  onStatus?:        (connected: boolean) => void;
  onDeath?:         (agentName: string, cause: string, day: number) => void;
  onBuildComplete?: (projectName: string, day: number) => void;
}

export class EventHandler {
  private _world:        IsoWorld;
  private _chars:        CharacterManager;
  private _pathFinder:   PathFinder;
  private _construction: ConstructionManager;
  private _callbacks:    UICallbacks;

  constructor(
    world:        IsoWorld,
    chars:        CharacterManager,
    pathFinder:   PathFinder,
    construction: ConstructionManager,
    callbacks:    UICallbacks = {},
  ) {
    this._world        = world;
    this._chars        = chars;
    this._pathFinder   = pathFinder;
    this._construction = construction;
    this._callbacks    = callbacks;
  }

  handle(event: WSEvent): void {
    switch (event.type) {

      case "state":
        this._onState(event as WSEvent & { type: "state" });
        break;

      case "tile_placed":
        this._onTilePlaced(event as TilePlacedEvent);
        break;

      case "tile_removed":
        this._onTileRemoved(event as TileRemovedEvent);
        break;

      case "construction_progress":
        this._onConstructionProgress(event as ConstructionProgressEvent);
        break;

      case "construction_complete":
        this._onConstructionComplete(event as WSEvent & { type: "construction_complete" });
        break;

      case "agent_state":
        this._onAgentState(event as AgentStateEvent);
        break;

      case "positions":
        this._onPositions(event as PositionsEvent);
        break;

      case "death":
        this._onDeath(event as WSEvent & { type: "death" });
        break;

      case "birth": {
        const b = event as WSEvent & { type: "birth"; agent: Agent };
        if (b.agent) this._chars.addAgent(b.agent);
        break;
      }

      case "message":
        this._onMessage(event as MessageEvent);
        break;

      case "meeting":
        this._onMeeting(event as MeetingEvent);
        break;

      case "time_phase":
      case "agent_update":
        break;

      default:
        if ((import.meta as { env?: { DEV?: boolean } }).env?.DEV) {
          console.debug("[EventHandler] unhandled:", event.type);
        }
    }
  }

  // ── Handlers ───────────────────────────────────────────────────────────────

  private _onState(event: WSEvent & { type: "state" }): void {
    const data = event.data as { agents?: Agent[] };
    if (data.agents && data.agents.length > 0) {
      this._chars.loadAgents(data.agents);
    }
    this._callbacks.onState?.(event);
  }

  private _onTilePlaced(event: TilePlacedEvent): void {
    // Update renderer — road auto-connect is handled inside IsoWorld.setTile()
    this._world.setTile(event.tile);
    // Update pathfinder walkability grid so agents route around new obstacles
    this._pathFinder.updateTile(event.tile);
  }

  private _onTileRemoved(event: TileRemovedEvent): void {
    // Remove tile from renderer (cell reverts to grass underneath)
    this._world.removeTile(event.col, event.row, event.layer);
    // Mark cell as walkable again in the pathfinder
    this._pathFinder.updateTile({
      col:       event.col,
      row:       event.row,
      tile_type: "grass",   // grass = walkable
      layer:     event.layer,
      built_by:  null,
      built_day: null,
    });
  }

  private _onConstructionProgress(event: ConstructionProgressEvent): void {
    // Delegate to ConstructionManager — handles progress bar, builder walk-to-site,
    // and stage tile swap.
    this._construction.onProgress(event);
    // Keep PathFinder aware: construction tiles are blocked
    if (event.project.stage > 0) {
      this._pathFinder.updateTile({
        col:       event.project.target_col,
        row:       event.project.target_row,
        tile_type: `construction_${event.project.stage}`,
        layer:     3,
        built_by:  event.project.builders[0] ?? null,
        built_day: event.day,
      });
    }
  }

  private _onConstructionComplete(event: WSEvent & { type: "construction_complete" }): void {
    const ev = event as unknown as ConstructionProgressEvent;
    const project = ev.project;

    // Tear down progress bar + stage sprite
    this._construction.onComplete(ev);

    if (project) {
      const tile = {
        col:       project.target_col,
        row:       project.target_row,
        tile_type: project.tile_type,
        layer:     3,
        built_by:  project.builders[0] ?? null,
        built_day: event.day as number,
      };
      // The tile_placed event that follows will also update IsoWorld,
      // but we set it here too for immediate visual feedback.
      this._world.setTile(tile);
      this._pathFinder.updateTile(tile);
    }
    this._callbacks.onBuildComplete?.(project?.name ?? "building", event.day as number);
  }

  private _onAgentState(event: AgentStateEvent): void {
    this._chars.setAgentState(event.name, event.action, event.x, event.y);
  }

  private _onPositions(event: PositionsEvent): void {
    this._chars.bulkUpdate(event.agents);
  }

  private _onDeath(event: WSEvent & { type: "death" }): void {
    const e = event as { type: "death"; agent: string; cause: string; day: number };
    this._chars.removeAgent(e.agent);
    this._callbacks.onDeath?.(e.agent, e.cause, e.day);
  }

  /**
   * message event — move the sender 35% of the way toward the recipient.
   * This makes every conversation physically visible on the iso map:
   * agents drift toward each other when they talk.
   */
  private _onMessage(event: MessageEvent): void {
    const senderPos    = this._chars.getPosition(event.from);
    const recipientPos = this._chars.getPosition(event.to);
    if (!senderPos || !recipientPos) return;

    const tCol = Math.round(senderPos.col + (recipientPos.col - senderPos.col) * 0.35);
    const tRow = Math.round(senderPos.row + (recipientPos.row - senderPos.row) * 0.35);
    this._chars.moveAgentTo(event.from, tCol, tRow);
  }

  /**
   * meeting event — both participants walk to the zone-centre position.
   * The backend enriches each meeting event with zone_x / zone_y
   * (zone centre in 96×72 Phase-5 space).  We convert to iso grid coords.
   */
  private _onMeeting(event: MeetingEvent): void {
    const { col, row } = scaleToGrid(event.zone_x, event.zone_y);
    for (const name of event.participants) {
      // Walk each participant to the meeting spot with a small random offset
      // so they don't all stack on the same tile.
      const jCol = col + Math.round((Math.random() - 0.5) * 4);
      const jRow = row + Math.round((Math.random() - 0.5) * 4);
      this._chars.moveAgentTo(name, jCol, jRow);
    }
  }
}
