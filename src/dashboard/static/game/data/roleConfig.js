/**
 * roleConfig.js — AIcity Phase 5
 * Role → visual config mapping.
 * tint: hex color applied to the placeholder agent sprite (colored square).
 * workZone: default location for this role.
 * label: 3-char abbreviation shown on the sprite.
 * criminal: true = active at night, dark zone movement.
 */

const ROLE_CONFIG = {
  builder: {
    tint:      0xFF8C00,   // orange
    workZone:  'LOC_BUILDER_YARD',
    label:     'BLD',
    criminal:  false,
  },
  explorer: {
    tint:      0x4CAF50,   // medium green
    workZone:  'LOC_EXPLORATION_TRAIL',
    label:     'EXP',
    criminal:  false,
  },
  police: {
    tint:      0x1565C0,   // navy blue
    workZone:  'LOC_POLICE_STATION',
    label:     'POL',
    criminal:  false,
  },
  merchant: {
    tint:      0xAB47BC,   // purple
    workZone:  'LOC_MARKET',
    label:     'MRC',
    criminal:  false,
  },
  teacher: {
    tint:      0xFDD835,   // yellow
    workZone:  'LOC_SCHOOL',
    label:     'TCH',
    criminal:  false,
  },
  healer: {
    tint:      0xF06292,   // pink
    workZone:  'LOC_CLINIC',
    label:     'HLR',
    criminal:  false,
  },
  messenger: {
    tint:      0x26C6DA,   // teal
    workZone:  'LOC_TOWN_SQUARE',
    label:     'MSG',
    criminal:  false,
  },
  lawyer: {
    tint:      0x78909C,   // blue-grey
    workZone:  'LOC_VAULT',
    label:     'LAW',
    criminal:  false,
  },
  thief: {
    tint:      0xE53935,   // red
    workZone:  'LOC_DARK_ALLEY',
    label:     'THF',
    criminal:  true,
  },
  newborn: {
    tint:      0x90CAF9,   // light blue
    workZone:  'LOC_SCHOOL',
    label:     'NEW',
    criminal:  false,
  },
  gang_leader: {
    tint:      0xFF5722,   // deep orange
    workZone:  'LOC_DARK_ALLEY',
    label:     'GNG',
    criminal:  true,
  },
  blackmailer: {
    tint:      0x7B1FA2,   // dark purple
    workZone:  'LOC_DARK_ALLEY',
    label:     'BLK',
    criminal:  true,
  },
  saboteur: {
    tint:      0x5D4037,   // brown-dark
    workZone:  'LOC_BUILDER_YARD',
    label:     'SAB',
    criminal:  true,
  },
};

// Fallback for unknown roles
const DEFAULT_ROLE_CONFIG = {
  tint:     0x888888,
  workZone: 'LOC_TOWN_SQUARE',
  label:    '???',
  criminal: false,
};

function getRoleConfig(role) {
  return ROLE_CONFIG[role] || DEFAULT_ROLE_CONFIG;
}
