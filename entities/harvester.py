"""
Harvester — collects spice and returns to refinery.
"""
from dataclasses import dataclass
from entities.unit import Unit, UnitState
from settings import UNIT_STATS


@dataclass
class Harvester(Unit):
    capacity: float = 1500.0
    harvest_rate: float = 50.0  # spice per second
    spice_carried: float = 0.0
    target_refinery_id: int = -1

    def __post_init__(self):
        stats = UNIT_STATS["harvester"]
        self.unit_type = "harvester"
        self.max_health = stats["health"]
        self.health = stats["health"]
        self.speed = stats["speed"]
        self.attack_damage = 0
        self.attack_range = 0
        self.size = stats["size"]
        self.capacity = stats["capacity"]
        self.harvest_rate = stats["harvest_rate"]

    @property
    def is_full(self) -> bool:
        return self.spice_carried >= self.capacity

    @property
    def is_empty(self) -> bool:
        return self.spice_carried <= 0

    @property
    def load_fraction(self) -> float:
        return self.spice_carried / max(1, self.capacity)

    def harvest_tick(self, dt: float, tile) -> float:
        """Harvest spice from a tile. Returns amount harvested."""
        if self.is_full:
            return 0
        amount = min(self.harvest_rate * dt, self.capacity - self.spice_carried)
        actual = tile.harvest(amount)
        self.spice_carried += actual
        return actual

    def deposit_spice(self) -> float:
        """Deposit all carried spice. Returns amount deposited."""
        amount = self.spice_carried
        self.spice_carried = 0
        return amount
