"""
Tile class — represents a single map cell.
"""
from dataclasses import dataclass


@dataclass
class Tile:
    x: int  # tile grid x
    y: int  # tile grid y
    terrain: str = "sand"  # sand, rock, dunes, spice, thick_spice, mountain
    spice: float = 0.0
    building_id: int = -1  # entity id of building occupying this tile, -1 = none

    @property
    def passable(self) -> bool:
        return self.terrain != "mountain" and self.building_id == -1

    @property
    def buildable(self) -> bool:
        return self.terrain == "rock" and self.building_id == -1

    @property
    def has_spice(self) -> bool:
        return self.spice > 0

    def harvest(self, amount: float) -> float:
        """Remove spice from tile, return actual amount harvested."""
        taken = min(amount, self.spice)
        self.spice -= taken
        if self.spice <= 0:
            self.spice = 0
            if self.terrain in ("spice", "thick_spice"):
                self.terrain = "sand"
        return taken

    def to_dict(self) -> dict:
        return {
            "x": self.x, "y": self.y,
            "type": self.terrain,
            "spice": self.spice
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Tile":
        return cls(
            x=data["x"], y=data["y"],
            terrain=data["type"],
            spice=data.get("spice", 0.0)
        )
