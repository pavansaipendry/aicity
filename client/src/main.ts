/**
 * main.ts — AIcity Phase 6 isometric client entry point
 *
 * Boot sequence:
 *   1. Init PixiJS v8 (async WebGL context)
 *   2. Create IsoWorld renderer + attach to stage
 *   3. Create Camera (pan + zoom)
 *   4. Create PathFinder (seeded after world loads)
 *   5. Create CharacterManager (renders + moves agents)
 *   6. Fetch /api/world → load tiles + seed PathFinder
 *   7. Open WebSocket → EventHandler routes events to IsoWorld + CharacterManager
 */

import { Application }           from "pixi.js";
import { IsoWorld }              from "@/engine/IsoWorld";
import { Camera }                from "@/engine/Camera";
import { WorldSocket }           from "@/ws/WorldSocket";
import { EventHandler }          from "@/systems/EventHandler";
import { PathFinder }            from "@/systems/PathFinder";
import { CharacterManager }      from "@/systems/CharacterManager";
import { ConstructionManager }   from "@/systems/ConstructionManager";
import { SpeechBubbleSystem }    from "@/systems/SpeechBubble";
import { AgentTooltip }          from "@/systems/AgentTooltip";
import { showLoading, hideLoading, showDisconnected, showReconnected } from "@/systems/Overlay";
import { Tile }                  from "@/types";

async function boot(): Promise<void> {
  showLoading();

  // ── 1. PixiJS v8 ─────────────────────────────────────────────────────────
  const app = new Application();
  await app.init({
    background:  0x0d1117,
    resizeTo:    window,
    antialias:   false,
    autoDensity: true,
    resolution:  window.devicePixelRatio || 1,
    preference:  "webgl",
  });

  document.getElementById("pixi-root")!.appendChild(app.canvas);

  // ── 2. IsoWorld renderer ─────────────────────────────────────────────────
  const world = new IsoWorld(app);
  app.stage.addChild(world.container);
  app.stage.sortableChildren = true;

  // ── 3. Camera ────────────────────────────────────────────────────────────
  const camera = new Camera(app, world.container);

  // ── 4. PathFinder ────────────────────────────────────────────────────────
  const pathFinder = new PathFinder();

  // ── 5. CharacterManager ──────────────────────────────────────────────────
  const chars = new CharacterManager(app, world.container, pathFinder);

  // ── 5b. ConstructionManager ──────────────────────────────────────────────
  const construction = new ConstructionManager(world.container, world, chars);

  // ── 5c. SpeechBubbleSystem ─────────────────────────────────────────────
  const bubbles = new SpeechBubbleSystem(app, world.container);

  // ── 5d. AgentTooltip ────────────────────────────────────────────────────
  const tooltip = new AgentTooltip(app);
  chars.onAgentClick = (sx, sy, info) => tooltip.show(sx, sy, info);

  // ── 6. Load initial world + seed pathfinder ──────────────────────────────
  try {
    const resp  = await fetch("/api/world");
    const tiles = (await resp.json()) as Tile[];
    world.loadWorld(tiles);
    pathFinder.setTiles(tiles);
    console.log(`[boot] ${tiles.length} tiles loaded — PathFinder seeded`);
  } catch (err) {
    console.warn("[boot] could not load world tiles:", err);
  }

  // ── 7. WebSocket + EventHandler ──────────────────────────────────────────
  const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
  const wsUrl      = `${wsProtocol}://${window.location.host}/ws`;

  const socket  = new WorldSocket(wsUrl);
  const handler = new EventHandler(world, chars, pathFinder, construction, bubbles, {
    onState: (event) => {
      const data = event.data as { day: number; agents: unknown[] };
      console.log(`[state] Day ${data.day}, agents: ${data.agents.length}`);
      hideLoading();
    },
    onDeath: (name, cause, day) => {
      console.log(`[death] ${name} — ${cause} (Day ${day})`);
    },
    onBuildComplete: (name, day) => {
      console.log(`[build] ${name} completed (Day ${day})`);
    },
    panTo: (col, row) => camera.centerOnTile(col, row),
  });

  socket.on((event) => handler.handle(event));

  socket.onStatusChange = (connected) => {
    const dot = document.getElementById("ws-dot-v2");
    if (dot) dot.style.background = connected ? "#00ff41" : "#ff3131";
    if (connected) showReconnected(); else showDisconnected();
  };

  if (import.meta.env.DEV) {
    const w = window as unknown as Record<string, unknown>;
    w._aiworld        = world;
    w._aichars        = chars;
    w._aiconstruction = construction;
    w._aisocket       = socket;
    console.log("[dev] _aiworld, _aichars, _aiconstruction, _aisocket on window");
  }
}

boot().catch(console.error);
