"""
tools/generate_citymap.py
Generates:
  1. src/dashboard/static/game/data/citymap.json  — Tiled-format tilemap (96×72)
  2. src/dashboard/static/game/assets/tilesets/terrain.png   — 8 colored placeholder tiles
  3. src/dashboard/static/game/assets/tilesets/buildings.png — 4 colored placeholder tiles
  4. src/dashboard/static/game/assets/tilesets/nature.png    — 4 colored placeholder tiles

Run: python tools/generate_citymap.py
"""

import json
import pathlib
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).parent.parent
STATIC_GAME = ROOT / "src/dashboard/static/game"
DATA_DIR    = STATIC_GAME / "data"
TILES_DIR   = STATIC_GAME / "assets/tilesets"

DATA_DIR.mkdir(parents=True, exist_ok=True)
TILES_DIR.mkdir(parents=True, exist_ok=True)

MAP_W, MAP_H = 96, 72
TILE = 16   # pixels per tile in the asset

# ── Tile GID table ────────────────────────────────────────────────────────────
# terrain.png  — firstgid 1  — 8 tiles
GID_GRASS       = 1
GID_WATER       = 2
GID_COBBLE      = 3
GID_DIRT        = 4
GID_ALLEY       = 5
GID_BRIDGE      = 6
GID_SAND        = 7
GID_OUTSKIRTS   = 8

# buildings.png — firstgid 9  — 4 tiles
GID_FOUNDATION  = 9    # empty lot (visible outline, no building yet)
GID_BUILT       = 10   # completed building (used when asset_built fires)
GID_B_UNUSED1   = 11
GID_B_UNUSED2   = 12

# nature.png   — firstgid 13 — 4 tiles
GID_TREE        = 13
GID_BUSH        = 14
GID_FLOWER      = 15
GID_GRAVESTONE  = 16   # Sprint 6: placed on death

EMPTY = 0

# ── Placeholder PNG generation ────────────────────────────────────────────────

def make_tile(draw: ImageDraw.Draw, x: int, color: tuple, label: str = "", border: bool = True):
    """Draw a 16×16 placeholder tile at column x."""
    x0, y0, x1, y1 = x * TILE, 0, x * TILE + TILE - 1, TILE - 1
    draw.rectangle([x0, y0, x1, y1], fill=color)
    if border:
        draw.rectangle([x0, y0, x1, y1], outline=(0, 0, 0, 80))
    if label:
        draw.text((x0 + 2, y0 + 4), label[0], fill=(255, 255, 255, 160))


def gen_terrain_png():
    img = Image.new("RGBA", (128, 16), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    tiles = [
        ((76, 153, 0, 255),    "G"),   # 1 grass
        ((30, 100, 200, 255),  "W"),   # 2 water
        ((140, 140, 140, 255), "C"),   # 3 cobble
        ((139, 90, 43, 255),   "D"),   # 4 dirt
        ((40, 40, 40, 255),    "A"),   # 5 alley
        ((160, 130, 80, 255),  "B"),   # 6 bridge
        ((220, 200, 140, 255), "S"),   # 7 sand/bank
        ((180, 180, 150, 255), "O"),   # 8 outskirts
    ]
    for i, (color, label) in enumerate(tiles):
        make_tile(d, i, color, label)

    path = TILES_DIR / "terrain.png"
    img.save(path)
    print(f"✓ {path}")


def gen_buildings_png():
    img = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    tiles = [
        ((100, 80, 60, 255),   "F"),   # 9  foundation
        ((160, 120, 80, 255),  "B"),   # 10 built
        ((60, 60, 80, 255),    "P"),   # 11 (police station)
        ((200, 180, 50, 255),  "V"),   # 12 (vault)
    ]
    for i, (color, label) in enumerate(tiles):
        make_tile(d, i, color, label)

    path = TILES_DIR / "buildings.png"
    img.save(path)
    print(f"✓ {path}")


def gen_nature_png():
    img = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    tiles = [
        ((20, 100, 20, 255),   "T"),   # 13 tree
        ((50, 120, 50, 255),   "S"),   # 14 bush
        ((200, 180, 50, 255),  "F"),   # 15 flower
        ((160, 140, 130, 255), "G"),   # 16 gravestone
    ]
    for i, (color, label) in enumerate(tiles):
        make_tile(d, i, color, label)

    path = TILES_DIR / "nature.png"
    img.save(path)
    print(f"✓ {path}")


# ── Map layer generators ──────────────────────────────────────────────────────

def flat_grid(default_gid: int = EMPTY) -> list[int]:
    return [default_gid] * (MAP_W * MAP_H)


def idx(x: int, y: int) -> int:
    return y * MAP_W + x


def fill_rect(grid, x1, y1, x2, y2, gid):
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            if 0 <= x < MAP_W and 0 <= y < MAP_H:
                grid[idx(x, y)] = gid


def draw_hline(grid, y, x1, x2, gid):
    for x in range(x1, x2 + 1):
        if 0 <= x < MAP_W and 0 <= y < MAP_H:
            grid[idx(x, y)] = gid


def draw_vline(grid, x, y1, y2, gid):
    for y in range(y1, y2 + 1):
        if 0 <= x < MAP_W and 0 <= y < MAP_H:
            grid[idx(x, y)] = gid


def scatter(grid, x1, y1, x2, y2, gid, density: int = 3):
    """Place gid at every `density`-th tile in the rect."""
    import random
    rng = random.Random(42)  # deterministic seed
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            if 0 <= x < MAP_W and 0 <= y < MAP_H:
                if rng.randint(0, density) == 0:
                    grid[idx(x, y)] = gid


def gen_ground_layer() -> list[int]:
    g = flat_grid(GID_GRASS)

    # River column
    fill_rect(g, 3, 0, 6, 71, GID_WATER)

    # River banks
    draw_vline(g, 2,  0, 71, GID_SAND)
    draw_vline(g, 7,  0, 71, GID_SAND)

    # Bridge replaces water
    fill_rect(g, 3, 20, 6, 23, GID_BRIDGE)

    # Dark alley ground
    fill_rect(g, 64, 56, 82, 70, GID_ALLEY)

    # Whispering Caves
    fill_rect(g, 84, 62, 95, 71, GID_ALLEY)

    # Eastern outskirts
    fill_rect(g, 82, 14, 95, 58, GID_OUTSKIRTS)

    return g


def gen_paths_layer() -> list[int]:
    g = flat_grid(EMPTY)

    # Elm Street: y=25, x=7–82 (cobble)
    draw_hline(g, 25, 7, 82, GID_COBBLE)

    # Main Street: y=36, x=7–82 (cobble)
    draw_hline(g, 36, 7, 82, GID_COBBLE)

    # South Road: y=50, x=7–82 (dirt)
    draw_hline(g, 50, 7, 82, GID_DIRT)

    # River Road: x=7, y=25–64
    draw_vline(g, 7, 25, 64, GID_COBBLE)

    # Alley Cut: x=64, y=36–64
    draw_vline(g, 64, 36, 64, GID_ALLEY)

    return g


def gen_buildings_layer() -> list[int]:
    """Empty lot foundations at the predefined home and public building lots."""
    g = flat_grid(EMPTY)

    # Public building lots (plan section 3: Buildings table)
    public_lots = [
        (10, 33, 6, 4),   # market stall
        (9,  45, 8, 6),   # hospital
        (63, 45, 10, 6),  # school
        (56, 29, 4, 6),   # watchtower
        (9,  59, 8, 6),   # archive
    ]
    for (lx, ly, lw, lh) in public_lots:
        # Just the outline of the foundation (single-tile border)
        for x in range(lx, lx + lw):
            g[idx(x, ly)] = GID_FOUNDATION
            g[idx(x, ly + lh - 1)] = GID_FOUNDATION
        for y in range(ly + 1, ly + lh - 1):
            g[idx(lx, y)] = GID_FOUNDATION
            g[idx(lx + lw - 1, y)] = GID_FOUNDATION

    # Home lots — 5×4 each
    home_lots = [
        (20, 16), (26, 16), (32, 16), (38, 16), (44, 16), (50, 16),   # N row
        (30, 47), (36, 47), (42, 47), (48, 47),                         # S row
    ]
    for (hx, hy) in home_lots:
        for x in range(hx, hx + 5):
            g[idx(x, hy)] = GID_FOUNDATION
            g[idx(x, hy + 3)] = GID_FOUNDATION
        for y in range(hy + 1, hy + 3):
            g[idx(hx, y)] = GID_FOUNDATION
            g[idx(hx + 4, y)] = GID_FOUNDATION

    return g


def gen_decoration_layer() -> list[int]:
    g = flat_grid(EMPTY)

    # Northern wilderness: dense trees
    scatter(g, 0, 0, 15, 12, GID_TREE, density=2)    # dense forest left
    scatter(g, 16, 0, 60, 10, GID_TREE, density=5)   # open field sparse
    scatter(g, 61, 0, 95, 12, GID_TREE, density=3)   # forest edge right

    # Town square park: flowers + bushes
    scatter(g, 30, 27, 50, 33, GID_FLOWER, density=4)
    scatter(g, 28, 26, 52, 34, GID_BUSH,   density=6)

    # Eastern outskirts: sparse trees
    scatter(g, 82, 14, 95, 58, GID_BUSH, density=5)

    # South boundary
    scatter(g, 8, 60, 80, 71, GID_BUSH, density=7)

    return g


# ── Tilemap JSON assembly ─────────────────────────────────────────────────────

def make_layer(name: str, layer_id: int, data: list[int]) -> dict:
    return {
        "data":    data,
        "height":  MAP_H,
        "id":      layer_id,
        "name":    name,
        "opacity": 1,
        "type":    "tilelayer",
        "visible": True,
        "width":   MAP_W,
        "x":       0,
        "y":       0,
    }


def gen_citymap():
    tilemap = {
        "compressionlevel": -1,
        "height": MAP_H,
        "infinite": False,
        "layers": [
            make_layer("ground",     1, gen_ground_layer()),
            make_layer("paths",      2, gen_paths_layer()),
            make_layer("buildings",  3, gen_buildings_layer()),
            make_layer("decoration", 4, gen_decoration_layer()),
        ],
        "nextlayerid":  5,
        "nextobjectid": 1,
        "orientation":  "orthogonal",
        "renderorder":  "right-down",
        "tiledversion": "1.10.2",
        "tileheight":   TILE,
        "tilesets": [
            {
                "columns":     8,
                "firstgid":    1,
                "image":       "../assets/tilesets/terrain.png",
                "imageheight": TILE,
                "imagewidth":  128,
                "margin":      0,
                "name":        "terrain",
                "spacing":     0,
                "tilecount":   8,
                "tileheight":  TILE,
                "tilewidth":   TILE,
            },
            {
                "columns":     4,
                "firstgid":    9,
                "image":       "../assets/tilesets/buildings.png",
                "imageheight": TILE,
                "imagewidth":  64,
                "margin":      0,
                "name":        "buildings",
                "spacing":     0,
                "tilecount":   4,
                "tileheight":  TILE,
                "tilewidth":   TILE,
            },
            {
                "columns":     4,
                "firstgid":    13,
                "image":       "../assets/tilesets/nature.png",
                "imageheight": TILE,
                "imagewidth":  64,
                "margin":      0,
                "name":        "nature",
                "spacing":     0,
                "tilecount":   4,
                "tileheight":  TILE,
                "tilewidth":   TILE,
            },
        ],
        "tilewidth": TILE,
        "type":      "map",
        "version":   "1.10",
        "width":     MAP_W,
    }
    path = DATA_DIR / "citymap.json"
    path.write_text(json.dumps(tilemap, indent=2))
    print(f"✓ {path}  ({MAP_W}×{MAP_H} tiles, {len(tilemap['layers'])} layers)")


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating AIcity map assets...")
    gen_terrain_png()
    gen_buildings_png()
    gen_nature_png()
    gen_citymap()
    print("\nDone. Placeholder assets are ready.")
    print("To use real LPC assets, replace the PNG files in:")
    print(f"  {TILES_DIR}")
