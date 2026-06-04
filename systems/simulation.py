"""
Simulation — deterministic tick-based game loop.
"""
from core.game_state import GameState
from core.command import Command, CommandType
from systems.movement_system import MovementSystem
from systems.combat_system import CombatSystem
from systems.production_system import ProductionSystem
from systems.resource_system import ResourceSystem
from entities.unit import Unit
from entities.harvester import Harvester
from entities.mcv import MCV
from entities.building import Building
from settings import TILE_SIZE, TICK_RATE


class Simulation:
    def __init__(self, game_state: GameState, game_map):
        self.game_state = game_state
        self.game_map = game_map
        self.movement = MovementSystem(game_map)
        self.combat = CombatSystem(game_state, self.movement)
        self.production = ProductionSystem(game_state, game_map)
        self.resource = ResourceSystem(game_state, game_map, self.movement)
        self.tick_accumulator: float = 0.0
        self.tick_duration: float = 1.0 / TICK_RATE

    def update(self, dt: float):
        self.tick_accumulator += dt
        while self.tick_accumulator >= self.tick_duration:
            self._tick()
            self.tick_accumulator -= self.tick_duration

    def _tick(self):
        self.game_state.tick += 1
        dt = self.tick_duration
        commands = self.game_state.get_commands_for_tick(self.game_state.tick)
        for cmd in commands:
            self._execute_command(cmd)
        self.movement.update(dt, self.game_state.entities)
        self.combat.update(dt, self.game_state.entities)
        self.production.update(dt)
        self.resource.update(dt)
        self._check_win_condition()

    def _execute_command(self, cmd: Command):
        if cmd.command_type == CommandType.MOVE:
            for eid in cmd.entity_ids:
                entity = self.game_state.entities.get(eid)
                if entity and isinstance(entity, Unit) and entity.alive:
                    tx = int(cmd.target_x) if cmd.target_x is not None else 0
                    ty = int(cmd.target_y) if cmd.target_y is not None else 0
                    # Check if shift-queued (waypoint)
                    if cmd.params.get("waypoint"):
                        self.movement.issue_waypoint_move(entity, tx, ty)
                    else:
                        entity.waypoint_queue = []  # Clear waypoints on new move
                        entity.target_entity_id = None  # Explicit move disengages
                        self.movement.issue_move(entity, tx, ty)

        elif cmd.command_type == CommandType.ATTACK:
            for eid in cmd.entity_ids:
                entity = self.game_state.entities.get(eid)
                if entity and isinstance(entity, Unit) and entity.alive:
                    if cmd.target_entity_id:
                        self.combat.issue_attack(entity, cmd.target_entity_id)

        elif cmd.command_type == CommandType.STOP:
            for eid in cmd.entity_ids:
                entity = self.game_state.entities.get(eid)
                if entity and isinstance(entity, Unit):
                    entity.stop()

        elif cmd.command_type == CommandType.HARVEST:
            for eid in cmd.entity_ids:
                entity = self.game_state.entities.get(eid)
                if entity and isinstance(entity, Harvester) and entity.alive:
                    self.resource.send_harvester_to_harvest(entity)

        elif cmd.command_type == CommandType.BUILD_UNIT:
            unit_type = cmd.params.get("unit_type", "")
            for eid in cmd.entity_ids:
                entity = self.game_state.entities.get(eid)
                if entity and isinstance(entity, Building):
                    self.production.request_unit_production(entity, unit_type)

        elif cmd.command_type == CommandType.PLACE_BUILDING:
            building_type = cmd.params.get("building_type", "")
            tx = int(cmd.target_x) if cmd.target_x is not None else 0
            ty = int(cmd.target_y) if cmd.target_y is not None else 0
            self.production.start_building_placement(cmd.player_id, building_type, tx, ty)

        elif cmd.command_type == CommandType.DEPLOY_MCV:
            for eid in cmd.entity_ids:
                entity = self.game_state.entities.get(eid)
                if entity and isinstance(entity, MCV) and entity.alive:
                    self._deploy_mcv(entity)

    def _deploy_mcv(self, mcv: MCV):
        tx = mcv.tile_x - 1
        ty = mcv.tile_y - 1
        if mcv.check_can_deploy(self.game_map, mcv.tile_x, mcv.tile_y):
            self.game_state.remove_entity(mcv.entity_id)
            self.production.start_building_placement(mcv.owner_id, "construction_yard", tx, ty)

    def _check_win_condition(self):
        for pid, player in self.game_state.players.items():
            buildings = self.game_state.get_player_buildings(pid)
            if not buildings and self.game_state.tick > TICK_RATE * 5:
                other_pid = [p for p in self.game_state.players if p != pid]
                if other_pid:
                    self.game_state.game_over = True
                    self.game_state.winner = other_pid[0]
