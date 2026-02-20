/**
 * CharacterManager.ts — Agent rendering and movement
 *
 * Sprint 2 renders agents as programmatic isometric pawns:
 *   - Diamond-shaped base (matches tile footprint, role-colored)
 *   - Circular "head" above the base
 *   - Name label that fades out when zoomed out
 *   - Idle "bob" animation (oscillates y by 2px)
 *   - Smooth tile-to-tile movement via GSAP (400ms per tile)
 *   - A* pathfinding routes around water and trees
 *
 * When Kenney character sprites arrive (Sprint 3), swap _drawCharacter()
 * to use a Sprite instead of Graphics. Everything else stays identical.
 *
 * Role colors — each role is instantly recognisable:
 *   builder    → orange       police     → royal blue
 *   thief      → dark red     merchant   → gold
 *   teacher    → teal         healer     → pink
 *   messenger  → purple       explorer   → forest green
 *   lawyer     → slate        villain    → dark green
 *   gang       → red-orange   newborn    → light blue
 */

import { Application, Container, Graphics, Text, TextStyle } from "pixi.js";
import gsap from "gsap";
import { tileToWorld, depthOrder, TILE_W, TILE_H } from "@/engine/IsoGrid";
import { PathFinder } from "./PathFinder";
import { Agent, AgentAction, scaleToGrid } from "@/types";

// ── Role → colour mapping ────────────────────────────────────────────────────
const ROLE_COLOUR: Record<string, number> = {
  builder:     0xFF8C00,
  police:      0x4169E1,
  thief:       0x8B0000,
  merchant:    0xFFD700,
  teacher:     0x20B2AA,
  healer:      0xFF69B4,
  messenger:   0x9370DB,
  explorer:    0x228B22,
  lawyer:      0x708090,
  gang_leader: 0xFF4500,
  blackmailer: 0x2F4F4F,
  saboteur:    0x800000,
  newborn:     0xADD8E6,
};

const DEFAULT_COLOUR = 0xAAAAAA;

// Pawn geometry (relative to tile anchor)
const PAWN_BASE_W = TILE_W * 0.45;   // base diamond width
const PAWN_BASE_H = TILE_H * 0.45;   // base diamond height
const PAWN_HEAD_R = 6;               // head circle radius
const PAWN_HEIGHT = 18;              // height from base to head centre


// ── Internal agent entry ────────────────────────────────────────────────────
interface AgentEntry {
  container: Container;
  gfx:       Graphics;
  label:     Text;
  col:       number;
  row:       number;
  role:      string;
  action:    AgentAction;
  tween?:    gsap.core.Tween;
  bobOffset: number;   // current y offset from idle bob
}


export class CharacterManager {
  private _stage:      Container;
  private _pathFinder: PathFinder;
  private _agents:     Map<string, AgentEntry> = new Map();
  private _bobTime     = 0;

  constructor(app: Application, worldContainer: Container, pathFinder: PathFinder) {
    this._stage      = worldContainer;
    this._pathFinder = pathFinder;

    // Idle bob runs on every frame via PixiJS ticker
    app.ticker.add((ticker) => this._onTick(ticker.deltaTime));
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Load initial agents from the "state" WS event.
   * Spawns a pawn for each alive agent.
   */
  loadAgents(agents: Agent[]): void {
    for (const a of agents) {
      if (a.alive === false) continue;
      this._spawnAgent(a);
    }
  }

  /**
   * Handle a bulk "positions" event — move all agents to their new positions.
   * Fired 3× per day (morning, afternoon, evening) by the simulation.
   */
  bulkUpdate(positions: Array<{ name: string; x: number; y: number; role: string; status: string }>): void {
    for (const p of positions) {
      if (p.status === "dead") {
        this._removeAgent(p.name);
        continue;
      }
      const { col, row } = scaleToGrid(p.x, p.y);
      const entry = this._agents.get(p.name);

      if (!entry) {
        // Agent not spawned yet — create on first position event
        this._spawnAgentAt(p.name, p.role, col, row);
      } else {
        this._moveAgentTo(p.name, col, row);
      }
    }
  }

  /**
   * Handle an "agent_state" event — update action and optionally move.
   */
  setAgentState(name: string, action: AgentAction, x: number, y: number): void {
    const { col, row } = scaleToGrid(x, y);
    const entry = this._agents.get(name);
    if (!entry) return;

    entry.action = action;
    this._moveAgentTo(name, col, row);
  }

  /**
   * Remove an agent (on death event).
   */
  removeAgent(name: string): void {
    this._removeAgent(name);
  }

  /**
   * Spawn a newborn agent.
   */
  addAgent(agent: Agent): void {
    this._spawnAgent(agent);
  }

  // ── Private: spawning ──────────────────────────────────────────────────────

  private _spawnAgent(agent: Agent): void {
    let col = 32, row = 32; // default: centre of map
    if (agent.x !== undefined && agent.y !== undefined) {
      const g = scaleToGrid(agent.x, agent.y);
      col = g.col; row = g.row;
    } else if (agent.col !== undefined && agent.row !== undefined) {
      col = agent.col; row = agent.row;
    }
    this._spawnAgentAt(agent.name, agent.role, col, row);
  }

  private _spawnAgentAt(name: string, role: string, col: number, row: number): void {
    if (this._agents.has(name)) return; // already exists

    const container = new Container();
    const gfx       = new Graphics();
    const label      = this._makeLabel(name, role);

    container.addChild(gfx);
    container.addChild(label);
    container.sortableChildren = false;

    const { x, y } = tileToWorld(col, row);
    container.x = x;
    container.y = y;
    container.zIndex = depthOrder(col, row, 4); // layer 4 = above buildings

    this._drawCharacter(gfx, role);
    this._stage.addChild(container);

    this._agents.set(name, {
      container, gfx, label,
      col, row, role,
      action: "idle",
      bobOffset: 0,
    });
  }

  // ── Private: movement ──────────────────────────────────────────────────────

  private _moveAgentTo(name: string, toCol: number, toRow: number): void {
    const entry = this._agents.get(name);
    if (!entry) return;
    if (entry.col === toCol && entry.row === toRow) return;

    // Cancel any existing tween
    entry.tween?.kill();

    this._pathFinder.findPath(
      entry.col, entry.row, toCol, toRow,
      (path) => {
        if (!path || path.length === 0) {
          // No path to destination (e.g. target is water or a tree).
          // Stay at current position rather than warping onto a blocked tile.
          entry.action = "idle";
          return;
        }
        this._walkPath(name, path);
      }
    );
  }

  private _walkPath(name: string, path: Array<[number, number]>): void {
    const entry = this._agents.get(name);
    if (!entry || path.length === 0) return;

    const [nextCol, nextRow] = path[0];
    const target = tileToWorld(nextCol, nextRow);

    entry.action = "walking";

    entry.tween = gsap.to(entry.container, {
      x: target.x,
      y: target.y,
      duration: 0.4,
      ease: "none",
      onUpdate: () => {
        // Keep depth sort correct while moving
        entry.container.zIndex = depthOrder(nextCol, nextRow, 4);
      },
      onComplete: () => {
        entry.col = nextCol;
        entry.row = nextRow;
        entry.container.zIndex = depthOrder(nextCol, nextRow, 4);

        const remaining = path.slice(1);
        if (remaining.length > 0) {
          this._walkPath(name, remaining);
        } else {
          entry.action = "idle";
        }
      },
    });
  }

  // ── Private: rendering ─────────────────────────────────────────────────────

  /**
   * Draw a programmatic isometric pawn.
   * Shape: small iso diamond (base) + short "neck" line + filled circle (head).
   *
   * This is the Sprint 2 placeholder. Sprint 3 replaces this with:
   *   const sprite = new Sprite(Texture.from('character_robot_a'));
   *   sprite.tint = ROLE_COLOUR[role];
   */
  private _drawCharacter(gfx: Graphics, role: string): void {
    gfx.clear();
    const colour  = ROLE_COLOUR[role] ?? DEFAULT_COLOUR;
    const dark    = darken(colour, 0.6);
    const hw      = PAWN_BASE_W / 2;
    const hh      = PAWN_BASE_H / 2;

    // ── Base diamond (iso footprint) ───────────────────────────────────────
    // Left face
    gfx.poly([0, 0, -hw, hh, 0, hh * 2, 0, hh]).fill(dark);
    // Right face
    gfx.poly([0, 0, hw, hh, 0, hh * 2, 0, hh]).fill(darken(colour, 0.8));
    // Top face (bright)
    gfx.poly([0, 0, hw, hh, 0, hh * 2, -hw, hh]).fill(colour);

    // ── Head (circle) ────────────────────────────────────────────────────
    const headY = -PAWN_HEIGHT;
    gfx.circle(0, headY, PAWN_HEAD_R).fill(colour);
    // Small outline ring
    gfx.circle(0, headY, PAWN_HEAD_R).stroke({ width: 1.5, color: dark });

    // ── Neck line ────────────────────────────────────────────────────────
    gfx.moveTo(0, 0).lineTo(0, headY + PAWN_HEAD_R)
       .stroke({ width: 1.5, color: dark });
  }

  private _makeLabel(name: string, role: string): Text {
    const style = new TextStyle({
      fontFamily: "Share Tech Mono, monospace",
      fontSize:   9,
      fill:       0xffffff,
      stroke:     { color: 0x000000, width: 3 },
      align:      "center",
    });
    const text  = new Text({ text: `${name}\n${role}`, style });
    text.anchor.set(0.5, 1);
    text.y = -(PAWN_HEIGHT + PAWN_HEAD_R + 4); // just above head
    return text;
  }

  // ── Private: animation ─────────────────────────────────────────────────────

  /**
   * Called every frame by the PixiJS ticker.
   * Idle agents gently bob up and down (2px oscillation).
   * At zoom < 0.5 we hide labels to reduce clutter.
   */
  private _onTick(dt: number): void {
    this._bobTime += dt * 0.05;

    for (const [, entry] of this._agents) {
      if (entry.action === "idle") {
        const bob = Math.sin(this._bobTime + entry.col + entry.row) * 2;
        entry.gfx.y = bob;
      } else {
        entry.gfx.y = 0;
      }
    }
  }

  // ── Private: cleanup ───────────────────────────────────────────────────────

  private _removeAgent(name: string): void {
    const entry = this._agents.get(name);
    if (!entry) return;
    entry.tween?.kill();
    this._stage.removeChild(entry.container);
    entry.container.destroy({ children: true });
    this._agents.delete(name);
  }
}


// ── Helpers ────────────────────────────────────────────────────────────────

function darken(colour: number, factor: number): number {
  const r = Math.floor(((colour >> 16) & 0xff) * factor);
  const g = Math.floor(((colour >>  8) & 0xff) * factor);
  const b = Math.floor(((colour >>  0) & 0xff) * factor);
  return (r << 16) | (g << 8) | b;
}
