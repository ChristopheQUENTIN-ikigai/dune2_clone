"""
Soldier — light infantry unit.
"""
from dataclasses import dataclass
from entities.unit import Unit
from settings import UNIT_STATS


@dataclass
class Soldier(Unit):
    def __post_init__(self):
        stats = UNIT_STATS["soldier"]
        self.unit_type = "soldier"
        self.max_health = stats["health"]
        self.health = stats["health"]
        self.speed = stats["speed"]
        self.attack_damage = stats["attack_damage"]
        self.attack_range = stats["attack_range"]
        self.attack_cooldown = stats["attack_cooldown"]
        self.size = stats["size"]
