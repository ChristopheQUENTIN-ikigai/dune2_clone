"""
MCV — Mobile Construction Vehicle. Deploys into Construction Yard.
"""
from dataclasses import dataclass
from entities.unit import Unit, UnitState
from settings import UNIT_STATS


@dataclass
class MCV(Unit):
    can_deploy: bool = True

    def __post_init__(self):
        stats = UNIT_STATS["mcv"]
        self.unit_type = "mcv"
        self.max_health = stats["health"]
        self.health = stats["health"]
        self.speed = stats["speed"]
        self.attack_damage = 0
        self.attack_range = 0
        self.size = stats["size"]

    def check_can_deploy(self, game_map, tile_x: int, tile_y: int) -> bool:
        """Check if MCV can deploy at current position (needs 3x3 rock area)."""
        return game_map.can_place_building(tile_x - 1, tile_y - 1, 3, 3)
