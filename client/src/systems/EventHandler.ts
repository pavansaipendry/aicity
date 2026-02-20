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
 */

import {
  WSEvent, TilePlacedEvent, ConstructionProgressEvent,
  AgentStateEvent, PositionsEvent, Agent,
} from "@/types";
import { IsoWorld }         from "@/engine/IsoWorld";
import { CharacterManager } from "./CharacterManager";
import { PathFinder }       from "./PathFinder";

export interface UICallbacks {
  onState?:         (data: WSEvent & { type: "state" }) => void;
  onStatus?:        (connected: boolean) => void;
  onDeath?:         (agentName: string, cause: string, day: number) => void;
  onBuildComplete?: (projectName: string, day: number) => void;
}

export class EventHandler {
  private _world:      IsoWorld;
  private _chars:      CharacterManager;
  private _pathFinder: PathFinder;
  private _callbacks:  UICallbacks;

  constructor(
    world:       IsoWorld,
    chars:       CharacterManager,
    pathFinder:  PathFinder,
    callbacks:   UICallbacks = {},
  ) {
    this._world      = world;
    this._chars      = chars;
    this._pathFinder = pathFinder;
    this._callbacks  = callbacks;
  }

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

  private _onConstructionProgress(event: ConstructionProgressEvent): void {
    const { project } = event;
    const tile = {
      col:       project.target_col,
      row:       project.target_row,
      tile_type: `construction_${project.stage}`,
      layer:     3,
      built_by:  project.builders[0] ?? null,
      built_day: event.day,
    };
    this._world.setTile(tile);
    this._pathFinder.updateTile(tile);
  }

  private _onConstructionComplete(event: WSEvent & { type: "construction_complete" }): void {
    const project = (event as unknown as ConstructionProgressEvent).project;
    if (project) {
      const tile = {
        col:       project.target_col,
        row:       project.target_row,
        tile_type: project.tile_type,
        layer:     3,
        built_by:  project.builders[0] ?? null,
        built_day: event.day as number,
      };
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
}
