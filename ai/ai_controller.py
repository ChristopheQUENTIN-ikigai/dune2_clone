"""
AI Controller — economy build-up + coordinated squadron waves.

Instead of trickling units at the enemy one by one, the AI now:
  * gathers freshly built combat units at a rally point near its base,
  * launches them together as a *wave* once the squadron reaches a target
    size (so they arrive and fight as a coordinated group),
  * keeps several waves in flight, re-targeting each wave when its objective
    is destroyed, and
  * pulls the still-gathering squadron back to defend when the base is
    threatened.

Build/produce decisions come from Prolog when available, otherwise from the
Python fallback; squadron/wave management always runs in Python.
"""
from core.command import Command, CommandType
from core.game_state import GameState
from ai.prolog_bridge import PrologBridge
from entities.building import Building
from entities.unit import Unit, UnitState, tile_to_world, world_to_tile
from entities.harvester import Harvester
from entities.mcv import MCV
from settings import (AI_DECISION_INTERVAL, BUILDING_STATS, UNIT_STATS, TILE_SIZE,
                      MAP_WIDTH, MAP_HEIGHT)

# Unit types the AI will commit to offensive waves (everything that can shoot
# and is not a harvester/MCV). Derived from config so new combat units are
# picked up automatically.
COMBAT_TYPES = [t for t, s in UNIT_STATS.items()
                if s.get("attack_damage", 0) > 0 and t not in ("harvester", "mcv")]


def is_combat_unit(e):
    return (isinstance(e, Unit) and e.alive
            and not isinstance(e, (Harvester, MCV))
            and e.attack_damage > 0)


class AIController:
    BASE_WAVE_SIZE = 5      # squad size that triggers the first wave
    MAX_WAVE_SIZE = 14      # cap so it doesn't wait forever
    RALLY_DISTANCE = 6      # tiles from base toward enemy where units gather
    DEFEND_RADIUS = 13      # tiles around a building counted as "threatened"

    def __init__(self, game_state, game_map, player_id):
        self.game_state = game_state
        self.game_map = game_map
        self.player_id = player_id
        self.prolog = PrologBridge()
        self.tick_counter = 0
        self.aggressive = False
        self.waves = []            # list of {"ids": [...], "target": entity_id|None}
        self.squad_ids = []        # combat units currently gathering for next wave
        self.assigned = set()      # every unit id the AI has already tasked
        self.waves_launched = 0
        self._rally_cache = None

    # ------------------------------------------------------------------ #
    def update(self):
        self.tick_counter += 1
        if self.tick_counter < AI_DECISION_INTERVAL:
            return
        self.tick_counter = 0
        self.aggressive = False
        if self.prolog.active:
            self._prolog_decision()
        else:
            self._fallback_decision()
        # Offensive coordination always runs (independent of build brain).
        self._manage_squadrons()

    def _prolog_decision(self):
        self.prolog.assert_game_state(self.game_state, self.player_id, self.game_map)
        for action, target in self.prolog.query_decisions():
            if action == "build":
                self._do_build(target)
            elif action in ("produce", "produce_priority"):
                self._do_produce(target)
            elif action == "attack":
                self.aggressive = True
        # Make sure the economy keeps expanding even under Prolog control.
        self._economy_buildout()

    # ------------------------------------------------------------------ #
    def _fallback_decision(self):
        player = self.game_state.players[self.player_id]
        buildings = self.game_state.get_player_buildings(self.player_id)
        units = self.game_state.get_player_units(self.player_id)
        btypes = {b.building_type for b in buildings}
        ccount = lambda t: sum(1 for u in units if u.unit_type == t)
        harvesters = ccount("harvester")

        # --- BUILD ORDER (independent checks; only one placement per call via
        #     _do_build's early return is fine — next cycle continues). ---
        if "barracks" not in btypes and player.credits >= 400:
            self._do_build("barracks")
        if player.power_balance < 20 and player.credits >= 500:
            self._do_build("solar_plant")
        if "refinery" not in btypes and player.credits >= 1500:
            self._do_build("refinery")
        self._economy_buildout()

        # --- PRODUCTION ---
        if harvesters < 2 and "refinery" in btypes and player.credits >= 500:
            self._do_produce("harvester")
        # Maintain a mix of forces from whatever factories exist.
        if "barracks" in btypes:
            if ccount("soldier") < 8 and player.credits >= 60:
                self._do_produce("soldier")
            if ccount("sniper") < 3 and player.credits >= 150:
                self._do_produce("sniper")
        if "light_factory" in btypes and player.credits >= 250:
            if ccount("trike") + ccount("quad") < 6:
                self._do_produce("trike" if ccount("trike") <= ccount("quad") else "quad")
        if "heavy_factory" in btypes and player.credits >= 600:
            if ccount("tank") < 5:
                self._do_produce("tank")
            elif ccount("rocket_launcher") < 3 and player.credits >= 800:
                self._do_produce("rocket_launcher")
        if "hi_tech" in btypes and ccount("helicopter") < 3 and player.credits >= 700:
            self._do_produce("helicopter")
        if "airfield" in btypes and player.credits >= 900:
            if ccount("jet_fighter") < 2:
                self._do_produce("jet_fighter")
            elif ccount("bomber") < 2 and player.credits >= 1200:
                self._do_produce("bomber")

    def _economy_buildout(self):
        """Expand the tech tree as credits allow (called from both brains)."""
        player = self.game_state.players[self.player_id]
        buildings = self.game_state.get_player_buildings(self.player_id)
        btypes = {b.building_type for b in buildings}
        turrets = sum(1 for b in buildings if b.building_type == "gun_turret")
        if "refinery" in btypes and turrets < 2 and player.credits >= 800:
            self._do_build("gun_turret")
        if "barracks" in btypes and "light_factory" not in btypes and player.credits >= 900:
            self._do_build("light_factory")
        if "refinery" in btypes and "heavy_factory" not in btypes and player.credits >= 2100:
            self._do_build("heavy_factory")
        if "heavy_factory" in btypes and "hi_tech" not in btypes and player.credits >= 1800:
            self._do_build("hi_tech")
        if "hi_tech" in btypes and "airfield" not in btypes and player.credits >= 2200:
            self._do_build("airfield")

    # ================================================================== #
    # SQUADRON / WAVE MANAGEMENT
    # ================================================================== #
    def _manage_squadrons(self):
        gs = self.game_state
        # 1. Drop dead units from every wave; retarget waves whose objective fell.
        live_waves = []
        for wave in self.waves:
            wave["ids"] = [i for i in wave["ids"]
                           if i in gs.entities and gs.entities[i].alive]
            if not wave["ids"]:
                continue
            tgt = gs.entities.get(wave["target"]) if wave["target"] else None
            if not tgt or not tgt.alive:
                new_t = self._pick_target()
                wave["target"] = new_t
                if new_t is not None:
                    self._command_attack(wave["ids"], new_t)
            live_waves.append(wave)
        self.waves = live_waves

        # 2. Refresh the gathering squad: add any new, unassigned combat units.
        self.squad_ids = [i for i in self.squad_ids
                          if i in gs.entities and gs.entities[i].alive]
        for e in gs.get_player_units(self.player_id):
            if is_combat_unit(e) and e.entity_id not in self.assigned:
                self.assigned.add(e.entity_id)
                self.squad_ids.append(e.entity_id)

        # 3. Defense overrides gathering: if the base is threatened, send the
        #    squad (not the committed waves) at the closest intruder.
        threat = self._nearest_threat()
        if threat is not None and self.squad_ids:
            self._command_attack(self.squad_ids, threat.entity_id)
            return

        # 4. Otherwise gather the squad at the rally point.
        rally = self._rally_tile()
        for i in self.squad_ids:
            u = gs.entities.get(i)
            if not u:
                continue
            if u.state == UnitState.IDLE:
                rx, ry = tile_to_world(*rally)
                if u.distance_to_point(rx, ry) > TILE_SIZE * 3:
                    gs.queue_command(Command(gs.tick, self.player_id,
                                             CommandType.MOVE, [i],
                                             target_x=rally[0], target_y=rally[1]))

        # 5. Launch a wave when the squad is big enough (smaller if aggressive).
        threshold = self.BASE_WAVE_SIZE + min(self.waves_launched, 4)
        threshold = min(threshold, self.MAX_WAVE_SIZE)
        if self.aggressive:
            threshold = max(3, threshold - 2)
        if len(self.squad_ids) >= threshold:
            target = self._pick_target()
            if target is not None:
                self._command_attack(self.squad_ids, target)
                self.waves.append({"ids": list(self.squad_ids), "target": target})
                self.waves_launched += 1
                self.squad_ids = []

    def _command_attack(self, ids, target_id):
        ids = [i for i in ids if i in self.game_state.entities
               and self.game_state.entities[i].alive]
        if not ids:
            return
        self.game_state.queue_command(Command(
            self.game_state.tick, self.player_id, CommandType.ATTACK,
            ids, target_entity_id=target_id))

    def _pick_target(self):
        """Choose a shared objective so the wave converges as a group:
        enemy Construction Yard > nearest enemy building > nearest enemy unit."""
        gs = self.game_state
        enemy_ids = [p for p in gs.players if p != self.player_id]
        if not enemy_ids:
            return None
        eid = enemy_ids[0]
        blds = gs.get_player_buildings(eid)
        units = gs.get_player_units(eid)
        rx, ry = self._rally_tile()
        for b in blds:
            if b.building_type == "construction_yard":
                return b.entity_id
        if blds:
            return min(blds, key=lambda b: abs(b.tile_x - rx) + abs(b.tile_y - ry)).entity_id
        if units:
            return min(units, key=lambda u: abs(u.tile_x - rx) + abs(u.tile_y - ry)).entity_id
        return None

    def _nearest_threat(self):
        """Closest living enemy entity within DEFEND_RADIUS of any of our
        buildings, or None."""
        gs = self.game_state
        my_blds = gs.get_player_buildings(self.player_id)
        if not my_blds:
            return None
        enemy_ids = [p for p in gs.players if p != self.player_id]
        if not enemy_ids:
            return None
        best, best_d = None, float("inf")
        for e in gs.get_player_entities(enemy_ids[0]):
            if not e.alive:
                continue
            etx = e.tile_x if isinstance(e, Unit) else (e.tile_x + e.size_w // 2)
            ety = e.tile_y if isinstance(e, Unit) else (e.tile_y + e.size_h // 2)
            for b in my_blds:
                d = abs(etx - (b.tile_x + b.size_w // 2)) + abs(ety - (b.tile_y + b.size_h // 2))
                if d <= self.DEFEND_RADIUS and d < best_d:
                    best, best_d = e, d
        return best

    def _rally_tile(self):
        """A staging tile a few tiles from our base toward the enemy base."""
        gs = self.game_state
        my_blds = gs.get_player_buildings(self.player_id)
        if not my_blds:
            return (MAP_WIDTH // 2, MAP_HEIGHT // 2)
        cy = next((b for b in my_blds if b.building_type == "construction_yard"), my_blds[0])
        bx, by = cy.tile_x + cy.size_w // 2, cy.tile_y + cy.size_h // 2
        enemy_ids = [p for p in gs.players if p != self.player_id]
        ex, ey = bx, by
        if enemy_ids:
            eb = gs.get_player_buildings(enemy_ids[0])
            if eb:
                ex = sum(b.tile_x for b in eb) / len(eb)
                ey = sum(b.tile_y for b in eb) / len(eb)
        dx, dy = ex - bx, ey - by
        dist = max(1.0, (dx * dx + dy * dy) ** 0.5)
        rx = int(bx + dx / dist * self.RALLY_DISTANCE)
        ry = int(by + dy / dist * self.RALLY_DISTANCE)
        rx = max(0, min(MAP_WIDTH - 1, rx))
        ry = max(0, min(MAP_HEIGHT - 1, ry))
        if not self.game_map.is_passable(rx, ry):
            for r in range(1, 6):
                for ddx in range(-r, r + 1):
                    for ddy in range(-r, r + 1):
                        if self.game_map.is_passable(rx + ddx, ry + ddy):
                            return (rx + ddx, ry + ddy)
        return (rx, ry)

    # ================================================================== #
    # BUILD / PRODUCE HELPERS
    # ================================================================== #
    def _do_build(self, building_type):
        stats = BUILDING_STATS.get(building_type)
        if not stats:
            return
        player = self.game_state.players[self.player_id]
        if player.credits < stats["cost"]:
            return
        # Don't queue a second copy of a building that's already up or building.
        for b in self.game_state.get_player_buildings(self.player_id):
            if b.building_type == building_type and building_type not in (
                    "gun_turret", "solar_plant"):
                return
        cy = None
        for e in self.game_state.get_player_buildings(self.player_id):
            if e.building_type == "construction_yard":
                cy = e
                break
        if not cy:
            return
        size = stats["size_tiles"]
        for r in range(2, 16):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if abs(dx) != r and abs(dy) != r:
                        continue
                    tx, ty = cy.tile_x + dx, cy.tile_y + dy
                    if self.game_map.can_place_building(tx, ty, size[0], size[1]):
                        self.game_state.queue_command(Command(
                            self.game_state.tick, self.player_id,
                            CommandType.PLACE_BUILDING, target_x=tx, target_y=ty,
                            params={"building_type": building_type}))
                        return

    def _do_produce(self, unit_type):
        player = self.game_state.players[self.player_id]
        for e in self.game_state.get_player_buildings(self.player_id):
            if e.alive and e.built and unit_type in e.get_producible():
                self.game_state.queue_command(Command(
                    self.game_state.tick, self.player_id, CommandType.BUILD_UNIT,
                    [e.entity_id], params={"unit_type": unit_type}))
                return
