"""
Command objects represent all player/AI actions.
These are the ONLY way to mutate game state (lockstep-ready).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CommandType(Enum):
    MOVE = "move"
    ATTACK = "attack"
    ATTACK_MOVE = "attack_move"
    STOP = "stop"
    HARVEST = "harvest"
    RETURN_HARVEST = "return_harvest"
    BUILD_UNIT = "build_unit"
    PLACE_BUILDING = "place_building"
    DEPLOY_MCV = "deploy_mcv"
    SET_RALLY = "set_rally"


@dataclass
class Command:
    tick: int
    player_id: int
    command_type: CommandType
    entity_ids: list[int] = field(default_factory=list)
    target_x: Optional[float] = None
    target_y: Optional[float] = None
    target_entity_id: Optional[int] = None
    params: dict = field(default_factory=dict)

    def __repr__(self):
        return (f"Command(tick={self.tick}, player={self.player_id}, "
                f"type={self.command_type.value}, entities={self.entity_ids})")
