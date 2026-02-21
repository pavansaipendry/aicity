/**
 * ConstructionManager.ts — Visual construction system
 *
 * Sprint 4 responsibility:
 *   - Receives `construction_progress` events from the backend.
 *   - Shows a floating progress bar above the construction site.
 *   - Walks the builder agent to the site via CharacterManager.
 *   - Swaps the stage tile (construction_1 … construction_5) via IsoWorld.
 *   - Cleans up the progress bar when `construction_complete` fires.
 *
 * Stage tile mapping (matches TILE_COLOURS in IsoWorld.ts):
 *   stage 0 — nothing (project is just planned)
 *   stage 1 — construction_1 (stakes in ground)
 *   stage 2 — construction_2 (foundation slab)
 *   stage 3 — construction_3 (framing)
 *   stage 4 — construction_4 (walls / finishing)
 *   stage 5 — complete — EventHandler puts the real building tile via tile_placed
 *
 * Progress bar design:
 *   - Thin pill shape: background (grey) + foreground (orange fill).
 *   - Label: "Market Stall 60%" floated above the building footprint.
 *   - Fades out when the project completes.
 */

import { Container, Graphics, Text, TextStyle } from "pixi.js";
import { tileToWorld } from "@/engine/IsoGrid";
import { IsoWorld } from "@/engine/IsoWorld";
import { CharacterManager } from "./CharacterManager";
import { ConstructionProgressEvent } from "@/types";

// Progress bar geometry
const BAR_W      = 60;   // full width in px
const BAR_H      = 6;    // height in px
const BAR_Y_OFF  = -36;  // above tile centre

interface SiteEntry {
  projectId:  number;
  name:       string;
  tileType:   string;
  col:        number;
  row:        number;
  stage:      number;
  builders:   string[];
  barGfx:     Graphics;
  barLabel:   Text;
  container:  Container;
}

export class ConstructionManager {
  private _stage:   Container;
  private _world:   IsoWorld;
  private _chars:   CharacterManager;
  private _sites:   Map<number, SiteEntry> = new Map();  // keyed by project id

  constructor(
    worldContainer: Container,
    world:          IsoWorld,
    chars:          CharacterManager,
  ) {
    this._stage = worldContainer;
    this._world = world;
    this._chars = chars;
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Handle a construction_progress WebSocket event.
   * Called by EventHandler on every daily tick broadcast.
   */
  onProgress(event: ConstructionProgressEvent): void {
    const { project, day } = event;
    const col   = project.target_col;
    const row   = project.target_row;
    const stage = project.stage;
    const id    = project.id;

    // Place or update the construction stage tile in IsoWorld
    if (stage > 0 && stage < 5) {
      this._world.setTile({
        col,
        row,
        tile_type: `construction_${stage}`,
        layer:     3,
        built_by:  project.builders[0] ?? null,
        built_day: day,
      });
    }

    const pct = Math.round((stage / project.total_stages) * 100);

    if (!this._sites.has(id)) {
      // First time we hear about this project — create the progress bar
      this._sites.set(id, this._createSite(id, project, pct));
    } else {
      // Update existing bar
      this._updateBar(id, pct, project.name);
    }

    // Walk each builder to the site so they look busy
    for (const builder of project.builders) {
      this._chars.moveAgentTo(builder, col, row);
    }
  }

  /**
   * Handle a construction_complete WebSocket event.
   * Called by EventHandler when stage reaches 5.
   * The final tile_placed event will be handled by IsoWorld directly —
   * we just need to tear down the progress bar.
   */
  onComplete(event: ConstructionProgressEvent): void {
    const id = event.project.id;
    this._removeSite(id);
  }

  // ── Private: site creation ─────────────────────────────────────────────────

  private _createSite(
    id:      number,
    project: ConstructionProgressEvent["project"],
    pct:     number,
  ): SiteEntry {
    const { x, y } = tileToWorld(project.target_col, project.target_row);
    const container = new Container();
    container.x = x;
    container.y = y + BAR_Y_OFF;

    const barGfx = new Graphics();
    const barLabel = this._makeLabel(project.name, pct);

    container.addChild(barGfx);
    container.addChild(barLabel);
    this._stage.addChild(container);

    const entry: SiteEntry = {
      projectId: id,
      name:      project.name,
      tileType:  project.tile_type,
      col:       project.target_col,
      row:       project.target_row,
      stage:     project.stage,
      builders:  project.builders,
      barGfx,
      barLabel,
      container,
    };

    this._drawBar(barGfx, pct);
    return entry;
  }

  private _updateBar(id: number, pct: number, name: string): void {
    const entry = this._sites.get(id);
    if (!entry) return;
    this._drawBar(entry.barGfx, pct);
    entry.barLabel.text = `${name} ${pct}%`;
  }

  private _drawBar(gfx: Graphics, pct: number): void {
    gfx.clear();
    const fillW = Math.round((BAR_W * pct) / 100);
    const x0    = -BAR_W / 2;

    // Background track
    gfx.roundRect(x0, 0, BAR_W, BAR_H, 3).fill(0x333333);
    // Filled portion — orange for in-progress, green when complete
    const fillColor = pct >= 100 ? 0x44cc44 : 0xFF8C00;
    if (fillW > 0) {
      gfx.roundRect(x0, 0, fillW, BAR_H, 3).fill(fillColor);
    }
    // Outline
    gfx.roundRect(x0, 0, BAR_W, BAR_H, 3).stroke({ width: 1, color: 0x000000 });
  }

  private _makeLabel(name: string, pct: number): Text {
    const style = new TextStyle({
      fontFamily: "Share Tech Mono, monospace",
      fontSize:   8,
      fill:       0xffffff,
      stroke:     { color: 0x000000, width: 2 },
      align:      "center",
    });
    const t = new Text({ text: `${name} ${pct}%`, style });
    t.anchor.set(0.5, 1);
    t.y = -2;   // just above bar
    return t;
  }

  private _removeSite(id: number): void {
    const entry = this._sites.get(id);
    if (!entry) return;
    this._stage.removeChild(entry.container);
    entry.container.destroy({ children: true });
    this._sites.delete(id);
  }
}
