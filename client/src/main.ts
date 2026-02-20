/**
 * main.ts — AIcity Phase 6 isometric client entry point
 *
 * Boot sequence:
 *   1. Init PixiJS v8 application (async — WebGL context setup)
 *   2. Create IsoWorld renderer + attach to stage
 *   3. Create Camera (binds mouse events)
 *   4. Fetch /api/world → load all tiles into IsoWorld
 *   5. Open WebSocket → EventHandler routes live events to IsoWorld
 *
 * Why async init?
 * PixiJS v8 uses WebGPU when available and falls back to WebGL.
 * Both require async context initialisation.
 * The old `new Application()` synchronous pattern was removed in v8.
 */

import { Application }    from "pixi.js";
import { IsoWorld }       from "@/engine/IsoWorld";
import { Camera }         from "@/engine/Camera";
import { WorldSocket }    from "@/ws/WorldSocket";
import { EventHandler }   from "@/systems/EventHandler";
import { Tile }           from "@/types";

async function boot(): Promise<void> {
  // ── 1. PixiJS application ──────────────────────────────────────────────────
  const app = new Application();
  await app.init({
    background:  0x0d1117,    // dark background (matches AIcity dark theme)
    resizeTo:    window,      // canvas fills the browser window
    antialias:   false,       // pixel-crisp iso tiles
    autoDensity: true,        // handle device pixel ratio (retina displays)
    resolution:  window.devicePixelRatio || 1,
    preference:  "webgl",     // WebGL first (WebGPU is still experimental)
  });

  // Attach the PixiJS canvas to the DOM
  document.getElementById("pixi-root")!.appendChild(app.canvas);

  // ── 2. IsoWorld renderer ──────────────────────────────────────────────────
  const world = new IsoWorld(app);
  app.stage.addChild(world.container);

  // ── 3. Camera ─────────────────────────────────────────────────────────────
  new Camera(app, world.container);

  // ── 4. Load initial world state from REST endpoint ─────────────────────────
  // Why REST instead of WebSocket?
  // The WS "state" event contains agent data.  World tiles are separate.
  // Fetching once via REST is simpler than buffering tile events before
  // the WS connection is established.
  try {
    const resp  = await fetch("/api/world");
    const tiles = (await resp.json()) as Tile[];
    world.loadWorld(tiles);
    console.log(`[boot] loaded ${tiles.length} tiles from /api/world`);
  } catch (err) {
    console.warn("[boot] could not load world tiles:", err);
    // Continue anyway — the grass plane is already drawn; tiles load via WS
  }

  // ── 5. WebSocket + EventHandler ─────────────────────────────────────────────
  // Use the same host:port as the page (works in both dev proxy and production).
  const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
  const wsUrl      = `${wsProtocol}://${window.location.host}/ws`;

  const socket = new WorldSocket(wsUrl);

  const handler = new EventHandler(world, {
    onState: (event) => {
      // Log state for now — Sprint 2 will wire this to the sidebar UI
      const data = event.data as { day: number; agents: unknown[] };
      console.log(`[state] Day ${data.day}, agents: ${data.agents.length}`);
    },
    onDeath: (name, cause, day) => {
      console.log(`[death] ${name} — ${cause} (Day ${day})`);
    },
    onBuildComplete: (name, day) => {
      console.log(`[build] ${name} completed (Day ${day})`);
    },
  });

  socket.on((event) => handler.handle(event));

  socket.onStatusChange = (connected) => {
    const dot = document.getElementById("ws-dot-v2");
    if (dot) dot.style.background = connected ? "#00ff41" : "#ff3131";
  };

  // Expose globals for debugging in the browser console during development
  if (import.meta.env.DEV) {
    const w = window as unknown as Record<string, unknown>;
    w._aiworld  = world;
    w._aisocket = socket;
    console.log("[dev] _aiworld and _aisocket exposed on window");
  }
}

boot().catch(console.error);
