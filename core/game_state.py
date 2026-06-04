"""
Central game state — the single source of truth.
All mutations happen through the simulation tick system.
"""
from dataclasses import dataclass, field
from typing import Optional
from core.player import Player
from core.command import Command


@dataclass
class GameState:
    """Holds all mutable game data."""
    tick: int = 0
    players: dict[int, Player] = field(default_factory=dict)
    entities: dict[int, object] = field(default_factory=dict)
    command_queue: list[Command] = field(default_factory=list)
    next_entity_id: int = 1
    game_over: bool = False
    winner: Optional[int] = None

    def new_entity_id(self) -> int:
        eid = self.next_entity_id
        self.next_entity_id += 1
        return eid

    def add_entity(self, entity) -> int:
        eid = self.new_entity_id()
        entity.entity_id = eid
        self.entities[eid] = entity
        # Register with player
        if entity.owner_id in self.players:
            self.players[entity.owner_id].entity_ids.append(eid)
        return eid

    def remove_entity(self, entity_id: int):
        entity = self.entities.pop(entity_id, None)
        if entity and entity.owner_id in self.players:
            player = self.players[entity.owner_id]
            if entity_id in player.entity_ids:
                player.entity_ids.remove(entity_id)

    def get_player_entities(self, player_id: int) -> list:
        return [self.entities[eid] for eid in self.players[player_id].entity_ids
                if eid in self.entities]

    def get_player_buildings(self, player_id: int) -> list:
        from entities.building import Building
        return [e for e in self.get_player_entities(player_id) if isinstance(e, Building)]

    def get_player_units(self, player_id: int) -> list:
        from entities.unit import Unit
        return [e for e in self.get_player_entities(player_id) if isinstance(e, Unit)]

    def queue_command(self, command: Command):
        self.command_queue.append(command)

    def get_commands_for_tick(self, tick: int) -> list[Command]:
        commands = [c for c in self.command_queue if c.tick <= tick]
        self.command_queue = [c for c in self.command_queue if c.tick > tick]
        return commands
