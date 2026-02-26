/**
 * Overlay.ts — Loading screen + WS disconnect banner
 *
 * Sprint 6: DOM-based overlays that sit above the PixiJS canvas.
 *
 * 1. Loading screen: shown on boot, hidden after first "state" event.
 * 2. WS disconnect banner: red bar at top when socket drops, green flash on reconnect.
 */

// ── Inject styles once ──────────────────────────────────────────────────────
const STYLE = document.createElement("style");
STYLE.textContent = `
  #ai-loading-screen {
    position: fixed; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    background: #0d1117; color: #00ff41;
    font-family: "Share Tech Mono", monospace;
    z-index: 10000;
    transition: opacity 0.6s ease;
  }
  #ai-loading-screen.hidden {
    opacity: 0; pointer-events: none;
  }
  #ai-loading-screen h1 {
    font-size: 2.4rem; margin-bottom: 0.5rem;
  }
  #ai-loading-screen p {
    font-size: 1rem; color: #8b949e;
  }
  @keyframes ai-pulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 1; }
  }
  #ai-loading-screen .dots {
    animation: ai-pulse 1.2s infinite;
  }

  #ai-ws-banner {
    position: fixed; top: 0; left: 0; right: 0;
    padding: 6px 16px;
    font-family: "Share Tech Mono", monospace;
    font-size: 0.85rem;
    text-align: center;
    z-index: 10001;
    transform: translateY(-100%);
    transition: transform 0.3s ease, background 0.3s ease;
  }
  #ai-ws-banner.show {
    transform: translateY(0);
  }
  #ai-ws-banner.disconnected {
    background: #ff3131; color: #fff;
  }
  #ai-ws-banner.connected {
    background: #00ff41; color: #0d1117;
  }
`;
document.head.appendChild(STYLE);


// ── Loading screen ──────────────────────────────────────────────────────────

function createLoadingScreen(): HTMLElement {
  const el = document.createElement("div");
  el.id = "ai-loading-screen";
  el.innerHTML = `
    <h1>AIcity</h1>
    <p class="dots">Loading world...</p>
  `;
  document.body.appendChild(el);
  return el;
}

let _loadingEl: HTMLElement | null = null;

export function showLoading(): void {
  if (!_loadingEl) _loadingEl = createLoadingScreen();
  _loadingEl.classList.remove("hidden");
}

export function hideLoading(): void {
  if (_loadingEl) {
    _loadingEl.classList.add("hidden");
    // Remove from DOM after fade
    setTimeout(() => {
      _loadingEl?.remove();
      _loadingEl = null;
    }, 700);
  }
}


// ── WS disconnect banner ────────────────────────────────────────────────────

function createBanner(): HTMLElement {
  const el = document.createElement("div");
  el.id = "ai-ws-banner";
  document.body.appendChild(el);
  return el;
}

let _bannerEl: HTMLElement | null = null;
let _hideTimer: ReturnType<typeof setTimeout> | null = null;

export function showDisconnected(): void {
  if (!_bannerEl) _bannerEl = createBanner();
  if (_hideTimer) { clearTimeout(_hideTimer); _hideTimer = null; }
  _bannerEl.textContent = "WebSocket disconnected — reconnecting...";
  _bannerEl.className = "show disconnected";
}

export function showReconnected(): void {
  if (!_bannerEl) _bannerEl = createBanner();
  if (_hideTimer) { clearTimeout(_hideTimer); _hideTimer = null; }
  _bannerEl.textContent = "Reconnected";
  _bannerEl.className = "show connected";
  // Auto-hide after 2s
  _hideTimer = setTimeout(() => {
    if (_bannerEl) _bannerEl.className = "";
  }, 2000);
}
