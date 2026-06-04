"""
Production system with queue support.
If building is busy, item goes into queue. Cost charged when production starts.
"""
from entities.building import Building
from entities.soldier import Soldier
from entities.harvester import Harvester
from entities.mcv import MCV
from entities.vehicle import make_unit
from entities.unit import tile_to_world
from settings import TILE_SIZE, UNIT_STATS, BUILDING_STATS


class ProductionSystem:
    def __init__(self, game_state, game_map):
        self.game_state = game_state
        self.game_map = game_map

    def request_unit_production(self, building: Building, unit_type: str) -> bool:
        """Request production. If busy, queues. Cost charged on start."""
        stats = UNIT_STATS.get(unit_type)
        if not stats:
            return False
        if not building.built:
            return False  # cannot produce from a building still under construction
        if unit_type not in building.get_producible():
            return False

        if building.producing:
            # Queue it (cost charged when it starts)
            if building.queue_full:
                return False
            return building.queue_production(unit_type)
        else:
            # Start immediately
            player = self.game_state.players[building.owner_id]
            if not player.spend_credits(stats["cost"]):
                return False
            building.start_production(unit_type, stats["build_time"])
            return True

    def start_building_placement(self, player_id, building_type, tile_x, tile_y):
        stats = BUILDING_STATS.get(building_type)
        if not stats:
            return False
        player = self.game_state.players[player_id]
        size = stats["size_tiles"]
        if not self.game_map.can_place_building(tile_x, tile_y, size[0], size[1]):
            return False
        if not player.spend_credits(stats["cost"]):
            return False
        # Place the building "under construction": it occupies its tiles
        # immediately (so nothing else can be built there) but is not yet
        # functional. A construction progress bar fills over build_time; power
        # and production only come online once it completes.
        build_time = float(stats.get("build_time", 0) or 0)
        built = build_time <= 0
        building = Building.create(building_type, player_id, tile_x, tile_y, built=built)
        if not built:
            building.construction_total_time = build_time
            building.construction_timer = 0.0
        eid = self.game_state.add_entity(building)
        self.game_map.place_building_tiles(tile_x, tile_y, size[0], size[1], eid)
        if built:
            self._apply_power(player, stats["power"])
        return True

    @staticmethod
    def _apply_power(player, power):
        player.power_produced += max(0, power)
        player.power_consumed += abs(min(0, power))

    def _complete_construction(self, building: Building):
        building.built = True
        building.build_progress = 1.0
        building.construction_timer = 0.0
        stats = BUILDING_STATS.get(building.building_type, {})
        player = self.game_state.players.get(building.owner_id)
        if player:
            self._apply_power(player, stats.get("power", 0))

    def update(self, dt):
        for entity in list(self.game_state.entities.values()):
            if not isinstance(entity, Building) or not entity.alive:
                continue

            # Advance any in-progress construction first.
            if not entity.built:
                if entity.update_construction(dt):
                    self._complete_construction(entity)
                continue  # under-construction buildings can't produce yet

            if entity.producing:
                result = entity.update_production(dt)
                if result:
                    self._spawn_unit(entity, result)
                    # Auto-start next in queue
                    self._try_start_next(entity)

            elif not entity.producing:
                # Try start from queue
                self._try_start_next(entity)

    def _try_start_next(self, building: Building):
        """Try to start next queued item, charging the player."""
        next_type = building.start_next_in_queue()
        if next_type:
            stats = UNIT_STATS.get(next_type) or BUILDING_STATS.get(next_type)
            if stats:
                player = self.game_state.players[building.owner_id]
                if player.spend_credits(stats.get("cost", 0)):
                    building.start_production(next_type, stats.get("build_time", 5))
                else:
                    # Can't afford — put back in queue front
                    building.production_queue.insert(0, next_type)

    def _spawn_unit(self, building, unit_type):
        stx, sty = self.game_map.find_spawn_tile(
            building.tile_x, building.tile_y, building.size_w, building.size_h)
        wx, wy = tile_to_world(stx, sty)
        self._create_unit(unit_type, building.owner_id, wx, wy)

    def _create_unit(self, unit_type, owner_id, wx, wy):
        unit = make_unit(unit_type, owner_id, wx, wy)
        if unit is None:
            return
        self.game_state.add_entity(unit)
