"""
Settings module — loads config.json and provides typed access to all game constants.
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
CONFIG_PATH = PROJECT_ROOT / "config.json"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r") as f:
        return json.load(f)


CONFIG = load_config()

# --- Window ---
WINDOW_TITLE = CONFIG["window"]["title"]
WINDOW_WIDTH = CONFIG["window"]["width"]
WINDOW_HEIGHT = CONFIG["window"]["height"]
WINDOW_MIN_WIDTH = CONFIG["window"]["min_width"]
WINDOW_MIN_HEIGHT = CONFIG["window"]["min_height"]
WINDOW_RESIZABLE = CONFIG["window"]["resizable"]
WINDOW_FULLSCREEN = CONFIG["window"]["fullscreen"]
WINDOW_VSYNC = CONFIG["window"]["vsync"]
FPS_CAP = CONFIG["window"]["fps_cap"]

# --- Map ---
MAP_WIDTH = CONFIG["map"]["width"]
MAP_HEIGHT = CONFIG["map"]["height"]
TILE_SIZE = CONFIG["map"]["tile_size"]
DEFAULT_MAP_PATH = PROJECT_ROOT / CONFIG["map"]["default_map"]
MAP_PIXEL_WIDTH = MAP_WIDTH * TILE_SIZE
MAP_PIXEL_HEIGHT = MAP_HEIGHT * TILE_SIZE

# --- Camera ---
SCROLL_SPEED = CONFIG["camera"]["scroll_speed"]
EDGE_SCROLL_MARGIN = CONFIG["camera"]["edge_scroll_margin"]
EDGE_SCROLL_SPEED = CONFIG["camera"]["edge_scroll_speed"]
ZOOM_MIN = CONFIG["camera"]["zoom_min"]
ZOOM_MAX = CONFIG["camera"]["zoom_max"]
ZOOM_STEP = CONFIG["camera"]["zoom_step"]

# --- Sidebar ---
SIDEBAR_WIDTH = CONFIG["sidebar"]["width"]

# --- Minimap ---
MINIMAP_WIDTH = CONFIG["minimap"]["width"]
MINIMAP_HEIGHT = CONFIG["minimap"]["height"]

# --- Gameplay ---
STARTING_CREDITS = CONFIG["gameplay"]["starting_credits"]
TICK_RATE = CONFIG["gameplay"]["tick_rate"]
AI_DECISION_INTERVAL = CONFIG["gameplay"]["ai_decision_interval_ticks"]
SPICE_PER_TILE_MIN = CONFIG["gameplay"]["spice_per_tile_min"]
SPICE_PER_TILE_MAX = CONFIG["gameplay"]["spice_per_tile_max"]
THICK_SPICE_MULTIPLIER = CONFIG["gameplay"]["thick_spice_multiplier"]

# --- Houses ---
HOUSES = CONFIG["houses"]

# --- Terrain ---
TERRAIN_COLORS = CONFIG["terrain_colors"]
TERRAIN_TYPES = list(TERRAIN_COLORS.keys())
PASSABLE_TERRAIN = {"sand", "dunes", "spice", "thick_spice", "rock"}
IMPASSABLE_TERRAIN = {"mountain"}
BUILDABLE_TERRAIN = {"rock"}

# --- Units ---
UNIT_STATS = CONFIG["units"]

# --- Buildings ---
BUILDING_STATS = CONFIG["buildings"]

# --- Keybindings ---
KEYBINDINGS = CONFIG["keybindings"]

# --- Paths ---
ASSETS_PATH = PROJECT_ROOT / CONFIG["paths"]["assets"]
TEXTURES_PATH = PROJECT_ROOT / CONFIG["paths"]["textures"]
MAPS_PATH = PROJECT_ROOT / CONFIG["paths"]["maps"]
SAVES_PATH = PROJECT_ROOT / CONFIG["paths"]["saves"]


def ensure_directories():
    for d in [ASSETS_PATH, TEXTURES_PATH, MAPS_PATH, SAVES_PATH,
              TEXTURES_PATH / "terrain", TEXTURES_PATH / "buildings",
              TEXTURES_PATH / "units", TEXTURES_PATH / "ui"]:
        d.mkdir(parents=True, exist_ok=True)
