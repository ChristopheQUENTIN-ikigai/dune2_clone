"""
Base entity — common attributes for all game objects.
"""
from dataclasses import dataclass, field


@dataclass
class Entity:
    entity_id: int = 0
    owner_id: int = 0
    x: float = 0.0  # pixel position
    y: float = 0.0
    health: int = 100
    max_health: int = 100
    selected: bool = False
    alive: bool = True

    @property
    def health_fraction(self) -> float:
        return self.health / max(1, self.max_health)

    def take_damage(self, amount: int):
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.alive = False

    def heal(self, amount: int):
        self.health = min(self.max_health, self.health + amount)
