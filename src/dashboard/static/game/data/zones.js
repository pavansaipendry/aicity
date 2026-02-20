/**
 * zones.js — AIcity Phase 5
 * LOC_* constants matching src/city/position_manager.py ZONES dict.
 * Each zone is { x1, y1, x2, y2 } in tile coordinates.
 * Center helpers computed on-demand.
 */

const ZONES = {
  LOC_WILDERNESS_N:     { x1:  0, y1:  0, x2: 96, y2: 12 },
  LOC_RIVER:            { x1:  3, y1:  0, x2:  6, y2: 72 },
  LOC_BRIDGE:           { x1:  3, y1: 20, x2:  6, y2: 23 },
  LOC_RESIDENTIAL_N:    { x1: 18, y1: 14, x2: 58, y2: 26 },
  LOC_TOWN_SQUARE:      { x1: 28, y1: 26, x2: 52, y2: 34 },
  LOC_MARKET:           { x1:  8, y1: 32, x2: 28, y2: 44 },
  LOC_POLICE_STATION:   { x1: 54, y1: 30, x2: 68, y2: 40 },
  LOC_BUILDER_YARD:     { x1: 64, y1: 14, x2: 82, y2: 28 },
  LOC_CLINIC:           { x1:  8, y1: 44, x2: 22, y2: 56 },
  LOC_RESIDENTIAL_S:    { x1: 28, y1: 44, x2: 58, y2: 56 },
  LOC_SCHOOL:           { x1: 62, y1: 44, x2: 80, y2: 56 },
  LOC_ARCHIVE:          { x1:  8, y1: 58, x2: 22, y2: 68 },
  LOC_VAULT:            { x1: 30, y1: 58, x2: 44, y2: 68 },
  LOC_DARK_ALLEY:       { x1: 64, y1: 58, x2: 82, y2: 68 },
  LOC_WHISPERING_CAVES: { x1: 84, y1: 62, x2: 96, y2: 72 },
  LOC_OUTSKIRTS_E:      { x1: 82, y1: 14, x2: 96, y2: 58 },
  LOC_EXPLORATION_TRAIL:{ x1: 20, y1:  0, x2: 96, y2: 14 },
};

/**
 * Returns the pixel-center of a zone for camera focus.
 * @param {string} zoneId — e.g. 'LOC_POLICE_STATION'
 * @param {number} tileSize — rendered tile size in pixels (default 32 = 16×zoom2)
 * @returns {{ x: number, y: number }}
 */
function getZoneCenter(zoneId, tileSize = 32) {
  const z = ZONES[zoneId];
  if (!z) return { x: 0, y: 0 };
  return {
    x: ((z.x1 + z.x2) / 2) * tileSize,
    y: ((z.y1 + z.y2) / 2) * tileSize,
  };
}

/**
 * Returns zone ID that contains the given tile coordinate.
 * @param {number} tx — tile x
 * @param {number} ty — tile y
 * @returns {string|null}
 */
function whichZone(tx, ty) {
  for (const [id, z] of Object.entries(ZONES)) {
    if (tx >= z.x1 && tx <= z.x2 && ty >= z.y1 && ty <= z.y2) {
      return id;
    }
  }
  return null;
}
