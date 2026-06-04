"""
Vehicle — generic combat unit (trike, quad, tank, rocket launcher, sniper)
and air units (helicopter, jet fighter, bomber).

A single data-driven class: all stats are read from config (UNIT_STATS) using
the unit_type passed to the constructor, so adding a new unit type only needs a
config entry plus (optionally) a texture. Air units set ``flying=True`` in
config; the movement system flies them in a straight line ignoring terrain,
while ground vehicles use normal A* pathfinding.
"""
from dataclasses import dataclass
from entities.unit import Unit
from settings import UNIT_STATS


@dataclass
class Vehicle(Unit):
    flying: bool = False
    splash: float = 0.0

    def __post_init__(self):
        stats = UNIT_STATS.get(self.unit_type)
        if not stats:
            return
        self.max_health = stats["health"]
        self.health = stats["health"]
        self.speed = stats["speed"]
        self.attack_damage = stats.get("attack_damage", 0)
        self.attack_range = stats.get("attack_range", 0)
        self.attack_cooldown = stats.get("attack_cooldown", 1.0)
        self.size = stats.get("size", 18)
        self.flying = bool(stats.get("flying", False))
        self.splash = float(stats.get("splash", 0.0))


def make_unit(unit_type: str, owner_id: int, x: float, y: float):
    """Factory: build the right entity instance for a unit type.

    Soldier/Harvester/MCV keep their dedicated classes (special behaviour);
    everything else is a data-driven Vehicle. Returns None for unknown types.
    """
    if unit_type not in UNIT_STATS:
        return None
    from entities.soldier import Soldier
    from entities.harvester import Harvester
    from entities.mcv import MCV
    if unit_type == "soldier":
        return Soldier(owner_id=owner_id, x=x, y=y)
    if unit_type == "harvester":
        return Harvester(owner_id=owner_id, x=x, y=y)
    if unit_type == "mcv":
        return MCV(owner_id=owner_id, x=x, y=y)
    return Vehicle(owner_id=owner_id, x=x, y=y, unit_type=unit_type)
