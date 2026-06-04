"""
Player state: house, credits, power, owned entities.
"""
from dataclasses import dataclass, field
from settings import STARTING_CREDITS


@dataclass
class Player:
    player_id: int
    house: str  # "atreides" or "harkonnen"
    is_ai: bool = False
    credits: float = STARTING_CREDITS
    power_produced: int = 0
    power_consumed: int = 0
    entity_ids: list[int] = field(default_factory=list)

    @property
    def power_balance(self) -> int:
        return self.power_produced - self.power_consumed

    @property
    def is_low_power(self) -> bool:
        return self.power_balance < 0

    def add_credits(self, amount: float):
        self.credits += amount

    def spend_credits(self, amount: float) -> bool:
        if self.credits >= amount:
            self.credits -= amount
            return True
        return False
