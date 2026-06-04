"""
Base unit with movement, attack, state machine, waypoint queue.
Unit x/y are in WORLD coords (Y-flipped: higher y = higher on screen).
tile_x/tile_y reverse the flip to get map tile indices.
"""
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from entities import Entity
from settings import TILE_SIZE, MAP_HEIGHT


class UnitState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    ATTACKING = "attacking"
    HARVESTING = "harvesting"
    RETURNING = "returning"
    DEPLOYING = "deploying"


def tile_to_world(tx, ty):
    """Convert tile coords to world pixel center."""
    return tx * TILE_SIZE + TILE_SIZE / 2, (MAP_HEIGHT - 1 - ty) * TILE_SIZE + TILE_SIZE / 2


def world_to_tile(wx, wy):
    """Convert world pixel coords to tile coords."""
    return int(wx // TILE_SIZE), MAP_HEIGHT - 1 - int(wy // TILE_SIZE)


@dataclass
class Unit(Entity):
    unit_type: str = "soldier"
    speed: float = 60.0
    attack_damage: int = 8
    attack_range: float = 2.0
    attack_cooldown: float = 1.0
    size: int = 12

    state: UnitState = UnitState.IDLE
    _move_state: str = ""
    path: list[tuple[int, int]] = field(default_factory=list)
    path_index: int = 0
    target_entity_id: Optional[int] = None
    attack_timer: float = 0.0
    waypoint_queue: list[tuple[int, int]] = field(default_factory=list)

    move_target_x: float = 0.0
    move_target_y: float = 0.0

    @property
    def tile_x(self) -> int:
        return int(self.x // TILE_SIZE)

    @property
    def tile_y(self) -> int:
        return MAP_HEIGHT - 1 - int(self.y // TILE_SIZE)

    @property
    def attack_range_pixels(self) -> float:
        return self.attack_range * TILE_SIZE

    @property
    def is_moving(self) -> bool:
        return len(self.path) > 0 and self.path_index < len(self.path)

    def set_path(self, path: list[tuple[int, int]], preserve_state: str = ""):
        self.path = path
        self.path_index = 0
        self._move_state = preserve_state
        if path:
            if not preserve_state:
                self.state = UnitState.MOVING
            self._set_next_waypoint()
        else:
            if not preserve_state:
                self.state = UnitState.IDLE

    def _set_next_waypoint(self):
        if self.path_index < len(self.path):
            tx, ty = self.path[self.path_index]
            wx, wy = tile_to_world(tx, ty)
            self.move_target_x = wx
            self.move_target_y = wy

    def update_movement(self, dt: float) -> bool:
        if not self.path or self.path_index >= len(self.path):
            return False
        dx = self.move_target_x - self.x
        dy = self.move_target_y - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 2.0:
            self.x = self.move_target_x
            self.y = self.move_target_y
            self.path_index += 1
            if self.path_index >= len(self.path):
                self.path = []
                if self.waypoint_queue:
                    return True
                if not self._move_state:
                    self.state = UnitState.IDLE
                self._move_state = ""
                return True
            self._set_next_waypoint()
            return False
        move_dist = self.speed * dt
        if move_dist >= dist:
            self.x = self.move_target_x
            self.y = self.move_target_y
        else:
            self.x += (dx / dist) * move_dist
            self.y += (dy / dist) * move_dist
        return False

    def update_attack(self, dt: float):
        if self.attack_timer > 0:
            self.attack_timer -= dt

    def can_attack(self) -> bool:
        return self.attack_timer <= 0 and self.attack_damage > 0

    def do_attack(self) -> int:
        self.attack_timer = self.attack_cooldown
        return self.attack_damage

    def distance_to(self, other) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def distance_to_point(self, px, py) -> float:
        return math.hypot(self.x - px, self.y - py)

    def stop(self):
        self.state = UnitState.IDLE
        self.path = []
        self.path_index = 0
        self.target_entity_id = None
        self.waypoint_queue = []
        self._move_state = ""

    def add_waypoint(self, tx: int, ty: int):
        self.waypoint_queue.append((tx, ty))
