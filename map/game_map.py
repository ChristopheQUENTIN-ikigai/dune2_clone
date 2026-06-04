"""
GameMap — 64x64 tile grid with JSON persistence, procedural generation,
and spawn point helpers.
"""
import json
import random
import math
from pathlib import Path
from typing import Optional

from map import Tile
from settings import (MAP_WIDTH, MAP_HEIGHT, TILE_SIZE,
                      SPICE_PER_TILE_MIN, SPICE_PER_TILE_MAX,
                      THICK_SPICE_MULTIPLIER)


def tile_to_world_center(tx, ty):
    """Tile coords -> world pixel center (Y-flipped)."""
    return tx * TILE_SIZE + TILE_SIZE / 2, (MAP_HEIGHT - 1 - ty) * TILE_SIZE + TILE_SIZE / 2


class GameMap:
    def __init__(self, width=MAP_WIDTH, height=MAP_HEIGHT):
        self.width = width
        self.height = height
        self.tiles = []
        self.starting_positions = []
        self._init_empty()

    def _init_empty(self):
        self.tiles = [[Tile(x=x, y=y, terrain="sand") for x in range(self.width)]
                      for y in range(self.height)]

    def get_tile(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x]
        return None

    def is_passable(self, tx, ty):
        tile = self.get_tile(tx, ty)
        return tile is not None and tile.passable

    def is_buildable(self, tx, ty):
        tile = self.get_tile(tx, ty)
        return tile is not None and tile.buildable

    def can_place_building(self, tx, ty, size_w, size_h):
        for dy in range(size_h):
            for dx in range(size_w):
                if not self.is_buildable(tx + dx, ty + dy):
                    return False
        return True

    def place_building_tiles(self, tx, ty, size_w, size_h, building_id):
        for dy in range(size_h):
            for dx in range(size_w):
                tile = self.get_tile(tx + dx, ty + dy)
                if tile:
                    tile.building_id = building_id

    def remove_building_tiles(self, tx, ty, size_w, size_h):
        for dy in range(size_h):
            for dx in range(size_w):
                tile = self.get_tile(tx + dx, ty + dy)
                if tile:
                    tile.building_id = -1

    def find_spawn_tile(self, building_tx, building_ty, building_sw, building_sh):
        """Find a passable tile near a building for unit spawning.
        Searches below the building first, then expanding ring."""
        # Prefer tiles just below (higher tile_y = below on map)
        for dy in range(0, 6):
            ty = building_ty + building_sh + dy
            for dx in range(-1, building_sw + 1):
                tx = building_tx + dx
                if self.is_passable(tx, ty):
                    return tx, ty
        # Expanding ring
        cx = building_tx + building_sw // 2
        cy = building_ty + building_sh // 2
        for r in range(1, 8):
            for ddx in range(-r, r + 1):
                for ddy in range(-r, r + 1):
                    if abs(ddx) != r and abs(ddy) != r:
                        continue
                    tx, ty = cx + ddx, cy + ddy
                    if self.is_passable(tx, ty):
                        return tx, ty
        return building_tx, building_ty + building_sh

    def find_nearest_spice(self, tx, ty, max_range=30):
        best = None
        best_dist = float('inf')
        for r in range(1, max_range + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if abs(dx) != r and abs(dy) != r:
                        continue
                    nx, ny = tx + dx, ty + dy
                    tile = self.get_tile(nx, ny)
                    if tile and tile.has_spice:
                        dist = abs(dx) + abs(dy)
                        if dist < best_dist:
                            best_dist = dist
                            best = (nx, ny)
            if best:
                return best
        return None

    def find_nearest_refinery(self, tx, ty, player_id, game_state):
        from entities.building import Building
        best_id = None
        best_dist = float('inf')
        for eid in game_state.players[player_id].entity_ids:
            entity = game_state.entities.get(eid)
            if entity and isinstance(entity, Building) and entity.building_type == "refinery":
                dist = abs(entity.tile_x - tx) + abs(entity.tile_y - ty)
                if dist < best_dist:
                    best_dist = dist
                    best_id = eid
        return best_id

    # --- Procedural Generation ---
    def generate_default(self):
        random.seed(12345)
        self._init_empty()
        self._place_rock_area(2, 2, 12, 10)
        self._place_rock_area(50, 52, 12, 10)
        for _ in range(8):
            rx = random.randint(5, self.width - 15)
            ry = random.randint(5, self.height - 15)
            self._place_rock_area(rx, ry, random.randint(4, 8), random.randint(4, 8))
        for _ in range(12):
            cx = random.randint(5, self.width - 5)
            cy = random.randint(5, self.height - 5)
            self._place_blob(cx, cy, random.randint(3, 7), "dunes")
        self._place_mountain_ridge(20, 10, 28, 18)
        self._place_mountain_ridge(36, 46, 44, 54)
        for _ in range(4):
            cx = random.randint(10, self.width - 10)
            cy = random.randint(10, self.height - 10)
            self._place_blob(cx, cy, random.randint(2, 3), "mountain")
        spice_centers = [(32, 20), (32, 44), (15, 35), (50, 30), (20, 50), (45, 15), (32, 32)]
        for sx, sy in spice_centers:
            self._place_spice_field(sx, sy, random.randint(4, 7))
        self.starting_positions = [
            {"player": 0, "x": 5, "y": 5},
            {"player": 1, "x": 56, "y": 56}
        ]

    def _place_rock_area(self, x, y, w, h):
        for dy in range(h):
            for dx in range(w):
                tile = self.get_tile(x + dx, y + dy)
                if tile and tile.terrain == "sand":
                    tile.terrain = "rock"

    def _place_blob(self, cx, cy, radius, terrain):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius + random.randint(-2, 2):
                    tile = self.get_tile(cx + dx, cy + dy)
                    if tile:
                        if terrain == "mountain" or tile.terrain not in ("mountain",):
                            tile.terrain = terrain

    def _place_mountain_ridge(self, x1, y1, x2, y2):
        steps = max(abs(x2 - x1), abs(y2 - y1))
        for i in range(steps):
            t = i / max(1, steps - 1)
            cx = int(x1 + (x2 - x1) * t + random.randint(-1, 1))
            cy = int(y1 + (y2 - y1) * t + random.randint(-1, 1))
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    tile = self.get_tile(cx + dx, cy + dy)
                    if tile:
                        tile.terrain = "mountain"

    def _place_spice_field(self, cx, cy, radius):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                dist = math.sqrt(dx * dx + dy * dy)
                if dist <= radius + random.uniform(-0.5, 0.5):
                    tile = self.get_tile(cx + dx, cy + dy)
                    if tile and tile.terrain in ("sand", "dunes"):
                        if dist <= radius * 0.4:
                            tile.terrain = "thick_spice"
                            tile.spice = random.uniform(
                                SPICE_PER_TILE_MIN * THICK_SPICE_MULTIPLIER,
                                SPICE_PER_TILE_MAX * THICK_SPICE_MULTIPLIER)
                        else:
                            tile.terrain = "spice"
                            tile.spice = random.uniform(SPICE_PER_TILE_MIN, SPICE_PER_TILE_MAX)

    def save_to_json(self, path):
        data = {"width": self.width, "height": self.height, "tiles": [],
                "starting_positions": self.starting_positions}
        for y in range(self.height):
            for x in range(self.width):
                tile = self.tiles[y][x]
                if tile.terrain != "sand" or tile.spice > 0:
                    data["tiles"].append(tile.to_dict())
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def load_from_json(self, path):
        with open(path, 'r') as f:
            data = json.load(f)
        self.width = data.get("width", MAP_WIDTH)
        self.height = data.get("height", MAP_HEIGHT)
        self._init_empty()
        for td in data.get("tiles", []):
            x, y = td["x"], td["y"]
            if 0 <= x < self.width and 0 <= y < self.height:
                self.tiles[y][x] = Tile.from_dict(td)
        self.starting_positions = data.get("starting_positions", [])
