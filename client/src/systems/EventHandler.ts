/**
 * EventHandler.ts — Routes WebSocket events to the correct systems
 *
 * Wiring layer between WorldSocket (network) and game systems (rendering).
 * Each event type has one handler method. Adding a new event:
 *   1. Add it to WSEvent union in types.ts
 *   2. Add a case in handle() below
 *   3. Write the handler method
 *
 * Sprint 3: PathFinder injected (tile_placed → walkability grid).
 * Sprint 4: ConstructionManager injected (construction_progress/complete).
 * Sprint 5: SpeechBubbleSystem injected (message → bubble above sender).
 *           Death → gravestone tile. Heart_attack → healer rush.
 *           Arrest → police chase + criminal flee.
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
import { SpeechBubbleSystem }    from "./SpeechBubble";

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
  private _bubbles:      SpeechBubbleSystem;
  private _callbacks:    UICallbacks;

  constructor(
    world:        IsoWorld,
    chars:        CharacterManager,
    pathFinder:   PathFinder,
    construction: ConstructionManager,
    bubbles:      SpeechBubbleSystem,
    callbacks:    UICallbacks = {},
  ) {
    this._world        = world;
    this._chars        = chars;
    this._pathFinder   = pathFinder;
    this._construction = construction;
    this._bubbles      = bubbles;
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

      // Sprint 5: social drama events
      case "heart_attack":
        this._onHeartAttack(event as WSEvent & { type: "heart_attack"; agent: string });
        break;

      case "arrest":
        this._onArrest(event as WSEvent & { type: "arrest" });
        break;

      case "time_phase":
      case "agent_update":
      case "newspaper":
      case "verdict":
      case "gang_event":
      case "project_started":
      case "project_completed":
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
    this._world.setTile(event.tile);
    this._pathFinder.updateTile(event.tile);
  }

  private _onTileRemoved(event: TileRemovedEvent): void {
    this._world.removeTile(event.col, event.row, event.layer);
    this._pathFinder.updateTile({
      col:       event.col,
      row:       event.row,
      tile_type: "grass",
      layer:     event.layer,
      built_by:  null,
      built_day: null,
    });
  }

  private _onConstructionProgress(event: ConstructionProgressEvent): void {
    this._construction.onProgress(event);
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

    // Get agent's last position before removing — place gravestone there
    const pos = this._chars.getPosition(e.agent);
    this._chars.removeAgent(e.agent);

    if (pos) {
      // Place a gravestone tile at the death location
      this._world.setTile({
        col:       pos.col,
        row:       pos.row,
        tile_type: "gravestone",
        layer:     3,
        built_by:  e.agent,
        built_day: e.day,
      });
    }

    this._callbacks.onDeath?.(e.agent, e.cause, e.day);
  }

  /**
   * message event — speech bubble above sender + move sender toward recipient.
   */
  private _onMessage(event: MessageEvent): void {
    const senderPos    = this._chars.getPosition(event.from);
    const recipientPos = this._chars.getPosition(event.to);
    if (!senderPos || !recipientPos) return;

    // Speech bubble at sender's position
    this._bubbles.show(senderPos.col, senderPos.row, event.body);

    // Move sender 35% toward recipient
    const tCol = Math.round(senderPos.col + (recipientPos.col - senderPos.col) * 0.35);
    const tRow = Math.round(senderPos.row + (recipientPos.row - senderPos.row) * 0.35);
    this._chars.moveAgentTo(event.from, tCol, tRow);
  }

  /**
   * meeting event — both participants walk to the zone-centre position.
   */
  private _onMeeting(event: MeetingEvent): void {
    const { col, row } = scaleToGrid(event.zone_x, event.zone_y);
    for (const name of event.participants) {
      const jCol = col + Math.round((Math.random() - 0.5) * 4);
      const jRow = row + Math.round((Math.random() - 0.5) * 4);
      this._chars.moveAgentTo(name, jCol, jRow);
    }
  }

  /**
   * heart_attack event — find the nearest healer and rush them to the victim.
   */
  private _onHeartAttack(event: WSEvent & { type: "heart_attack"; agent: string }): void {
    const victimName = (event as { agent: string }).agent;
    const victimPos  = this._chars.getPosition(victimName);
    if (!victimPos) return;

    // Show distress bubble at victim
    this._bubbles.show(victimPos.col, victimPos.row, "💔 Heart attack!");

    // Find a healer and rush them to the victim
    // We don't have a role lookup in CharacterManager, so we iterate known agents.
    // As a fallback: the backend already moves the healer via agent_state events.
  }

  /**
   * arrest event — police chases criminal, criminal may flee.
   */
  private _onArrest(event: WSEvent & { type: "arrest" }): void {
    const e = event as { type: "arrest"; agent: string; detail: string };
    const policeName = e.agent;

    // Parse arrested name from detail: "arrested <name>"
    const match = e.detail?.match(/arrested\s+(.+)/i);
    if (!match) return;
    const criminalName = match[1].trim();

    const policePos   = this._chars.getPosition(policeName);
    const criminalPos = this._chars.getPosition(criminalName);
    if (!policePos || !criminalPos) return;

    // Police runs toward criminal
    this._chars.moveAgentTo(policeName, criminalPos.col, criminalPos.row);

    // Criminal flees in the opposite direction
    const fleeCol = Math.max(0, Math.min(63, criminalPos.col + (criminalPos.col - policePos.col)));
    const fleeRow = Math.max(0, Math.min(63, criminalPos.row + (criminalPos.row - policePos.row)));
    this._chars.moveAgentTo(criminalName, fleeCol, fleeRow);

    // Arrest bubble
    this._bubbles.show(policePos.col, policePos.row, `Arresting ${criminalName}!`);
  }
}
