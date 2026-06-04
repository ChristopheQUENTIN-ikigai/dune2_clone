"""
Resource system — harvester only harvests on spice/thick_spice terrain.
"""
from entities.harvester import Harvester
from entities.unit import UnitState
from settings import TILE_SIZE


class ResourceSystem:
    def __init__(self, game_state, game_map, movement_system):
        self.game_state = game_state
        self.game_map = game_map
        self.movement_system = movement_system

    def update(self, dt):
        for entity in list(self.game_state.entities.values()):
            if isinstance(entity, Harvester) and entity.alive:
                self._update_harvester(entity, dt)

    def _update_harvester(self, h, dt):
        if h.state == UnitState.HARVESTING:
            if h.is_moving:
                return
            tile = self.game_map.get_tile(h.tile_x, h.tile_y)
            # ONLY harvest on spice or thick_spice terrain
            if tile and tile.terrain in ("spice", "thick_spice") and tile.has_spice and not h.is_full:
                h.harvest_tick(dt, tile)
            else:
                if h.is_full:
                    self._send_to_refinery(h)
                elif tile and not tile.has_spice:
                    # Tile ran out, find more
                    self._send_to_spice(h)
                elif not tile or tile.terrain not in ("spice", "thick_spice"):
                    # Wrong terrain, find spice
                    self._send_to_spice(h)

        elif h.state == UnitState.RETURNING:
            if h.is_moving:
                return
            if h.target_refinery_id >= 0:
                ref = self.game_state.entities.get(h.target_refinery_id)
                if ref and h.distance_to_point(ref.x, ref.y) < TILE_SIZE * 4:
                    amount = h.deposit_spice()
                    self.game_state.players[h.owner_id].add_credits(amount)
                    self._send_to_spice(h)
                else:
                    self._send_to_refinery(h)

        elif h.state == UnitState.IDLE:
            if h.is_full or h.load_fraction > 0.8:
                self._send_to_refinery(h)
            else:
                self._send_to_spice(h)

    def send_harvester_to_harvest(self, h):
        self._send_to_spice(h)

    def _send_to_spice(self, h):
        pos = self.game_map.find_nearest_spice(h.tile_x, h.tile_y)
        if pos:
            self.movement_system.issue_move(h, pos[0], pos[1], preserve_state="harvest")
            h.state = UnitState.HARVESTING
        else:
            h.state = UnitState.IDLE

    def _send_to_refinery(self, h):
        ref_id = self.game_map.find_nearest_refinery(h.tile_x, h.tile_y, h.owner_id, self.game_state)
        if ref_id is not None:
            ref = self.game_state.entities.get(ref_id)
            if ref:
                tx = ref.tile_x + ref.size_w // 2
                ty = ref.tile_y + ref.size_h // 2
                self.movement_system.issue_move(h, tx, ty, preserve_state="return")
                h.target_refinery_id = ref_id
                h.state = UnitState.RETURNING
                return
        h.state = UnitState.IDLE
