"""
Building base class with health, production queue, and power.
Queue: clicking produce while busy queues the item (up to 5).
"""
from dataclasses import dataclass, field
from typing import Optional
from entities import Entity
from settings import TILE_SIZE, MAP_HEIGHT, BUILDING_STATS


@dataclass
class Building(Entity):
    building_type: str = "construction_yard"
    tile_x: int = 0
    tile_y: int = 0
    size_w: int = 3
    size_h: int = 3
    power: int = 0
    built: bool = True
    build_progress: float = 1.0

    production_queue: list[str] = field(default_factory=list)
    production_timer: float = 0.0
    production_total_time: float = 0.0
    producing: Optional[str] = None

    # Construction progress (a placed building fills a progress bar over its
    # build_time before it becomes functional). built=True means complete.
    construction_timer: float = 0.0
    construction_total_time: float = 0.0

    # Combat (defensive structures such as the Gun Turret). Zero for normal buildings.
    attack_damage: int = 0
    attack_range: float = 0.0
    attack_cooldown: float = 0.0
    attack_timer: float = 0.0
    target_entity_id: Optional[int] = None

    MAX_QUEUE = 5

    @property
    def world_left(self) -> float:
        """World-space x of the building's left edge (Y-flipped world convention)."""
        return self.tile_x * TILE_SIZE

    @property
    def world_bottom(self) -> float:
        """World-space y of the building's bottom edge.

        tile_y is the TOP-LEFT tile. The footprint occupies tile rows
        tile_y .. tile_y + size_h - 1, which in the Y-flipped world map to the
        band whose bottom is (MAP_HEIGHT - tile_y - size_h) * TILE_SIZE. This is
        the single source of truth shared by rendering, picking, combat and the
        harvester deposit check so they never disagree.
        """
        return (MAP_HEIGHT - self.tile_y - self.size_h) * TILE_SIZE

    @property
    def pixel_x(self) -> float:
        """World-space x of the footprint center."""
        return self.world_left + (self.size_w * TILE_SIZE) / 2

    @property
    def pixel_y(self) -> float:
        """World-space y of the footprint center (Y-flipped)."""
        return self.world_bottom + (self.size_h * TILE_SIZE) / 2

    @property
    def attack_range_pixels(self) -> float:
        return self.attack_range * TILE_SIZE

    @property
    def is_combat(self) -> bool:
        return self.attack_damage > 0

    def update_attack(self, dt: float):
        if self.attack_timer > 0:
            self.attack_timer -= dt

    def can_attack(self) -> bool:
        return self.attack_timer <= 0 and self.attack_damage > 0

    def do_attack(self) -> int:
        self.attack_timer = self.attack_cooldown
        return self.attack_damage

    @property
    def can_produce(self) -> bool:
        if not self.built:
            return False
        stats = BUILDING_STATS.get(self.building_type, {})
        return len(stats.get("produces", [])) > 0

    @property
    def is_constructing(self) -> bool:
        return not self.built

    @property
    def construction_progress(self) -> float:
        if self.built:
            return 1.0
        if self.construction_total_time <= 0:
            return 1.0
        return min(1.0, self.construction_timer / self.construction_total_time)

    def update_construction(self, dt: float) -> bool:
        """Advance construction. Returns True on the tick it completes."""
        if self.built:
            return False
        if self.construction_total_time <= 0:
            self.built = True
            self.build_progress = 1.0
            return True
        self.construction_timer += dt
        self.build_progress = self.construction_progress
        if self.construction_timer >= self.construction_total_time:
            self.construction_timer = self.construction_total_time
            self.built = True
            self.build_progress = 1.0
            return True
        return False

    @property
    def production_progress(self) -> float:
        if self.production_total_time <= 0:
            return 0
        return min(1.0, self.production_timer / self.production_total_time)

    @property
    def queue_full(self) -> bool:
        return len(self.production_queue) >= self.MAX_QUEUE

    def get_producible(self) -> list[str]:
        stats = BUILDING_STATS.get(self.building_type, {})
        return stats.get("produces", [])

    def start_production(self, item_type: str, build_time: float):
        self.producing = item_type
        self.production_timer = 0.0
        self.production_total_time = build_time

    def queue_production(self, item_type: str) -> bool:
        """Add to queue. Returns True if queued successfully."""
        if self.queue_full:
            return False
        self.production_queue.append(item_type)
        return True

    def update_production(self, dt: float) -> Optional[str]:
        """Update production. Returns produced item type if complete."""
        if not self.producing:
            return None
        self.production_timer += dt
        if self.production_timer >= self.production_total_time:
            result = self.producing
            self.producing = None
            self.production_timer = 0
            self.production_total_time = 0
            return result
        return None

    def start_next_in_queue(self) -> Optional[str]:
        """Pop next item from queue. Returns item type or None."""
        if self.production_queue and not self.producing:
            return self.production_queue.pop(0)
        return None

    @classmethod
    def create(cls, building_type, owner_id, tile_x, tile_y, built=True):
        stats = BUILDING_STATS[building_type]
        size = stats["size_tiles"]
        b = cls(owner_id=owner_id, building_type=building_type,
                tile_x=tile_x, tile_y=tile_y,
                size_w=size[0], size_h=size[1],
                health=stats["health"], max_health=stats["health"],
                power=stats["power"], built=built,
                build_progress=1.0 if built else 0.0,
                attack_damage=stats.get("attack_damage", 0),
                attack_range=stats.get("attack_range", 0.0),
                attack_cooldown=stats.get("attack_cooldown", 0.0))
        b.x = b.pixel_x
        b.y = b.pixel_y
        return b
