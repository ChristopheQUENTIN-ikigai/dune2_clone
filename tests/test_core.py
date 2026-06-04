#!/usr/bin/env python3
"""Tests for core game systems."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.game_state import GameState
from core.player import Player
from core.command import Command, CommandType
from map.game_map import GameMap
from map.pathfinding import astar
from map import Tile
from entities.soldier import Soldier
from entities.harvester import Harvester
from entities.building import Building
from entities.mcv import MCV


def test_pathfinding():
    gm = GameMap()
    gm.generate_default()
    path = astar(gm, (5, 8), (15, 15))
    assert path is not None, "Path should be found"
    assert len(path) > 0, "Path should not be empty"
    assert path[0] == (5, 8), "Path should start at origin"
    assert path[-1] == (15, 15), "Path should end at goal"
    print("[PASS] test_pathfinding")


def test_pathfinding_no_path():
    gm = GameMap(10, 10)
    # Wall off the goal
    for x in range(10):
        gm.tiles[5][x].terrain = "mountain"
    path = astar(gm, (1, 1), (1, 8))
    assert path is None, "No path through mountains"
    print("[PASS] test_pathfinding_no_path")


def test_game_state():
    gs = GameState()
    gs.players[0] = Player(player_id=0, house="atreides")
    s = Soldier(owner_id=0, x=100, y=100)
    eid = gs.add_entity(s)
    assert eid == 1
    assert eid in gs.entities
    assert eid in gs.players[0].entity_ids
    gs.remove_entity(eid)
    assert eid not in gs.entities
    assert eid not in gs.players[0].entity_ids
    print("[PASS] test_game_state")


def test_player_credits():
    p = Player(player_id=0, house="atreides", credits=1000)
    assert p.spend_credits(500) is True
    assert p.credits == 500
    assert p.spend_credits(600) is False
    assert p.credits == 500
    p.add_credits(200)
    assert p.credits == 700
    print("[PASS] test_player_credits")


def test_tile_harvest():
    t = Tile(x=0, y=0, terrain="spice", spice=100)
    taken = t.harvest(30)
    assert taken == 30
    assert t.spice == 70
    taken = t.harvest(200)
    assert taken == 70
    assert t.spice == 0
    assert t.terrain == "sand"
    print("[PASS] test_tile_harvest")


def test_building_create():
    b = Building.create("construction_yard", 0, 5, 5)
    assert b.building_type == "construction_yard"
    assert b.size_w == 3
    assert b.size_h == 3
    assert b.health == 1500
    print("[PASS] test_building_create")


def test_soldier_combat():
    s1 = Soldier(owner_id=0, x=100, y=100)
    s2 = Soldier(owner_id=1, x=110, y=100)
    dmg = s1.do_attack()
    assert dmg == 8
    s2.take_damage(dmg)
    assert s2.health == 92
    assert s2.alive is True
    # Kill
    s2.take_damage(100)
    assert s2.alive is False
    print("[PASS] test_soldier_combat")


def test_harvester():
    h = Harvester(owner_id=0, x=100, y=100)
    assert h.is_empty is True
    assert h.is_full is False
    t = Tile(x=0, y=0, terrain="spice", spice=500)
    h.harvest_tick(1.0, t)
    assert h.spice_carried == 50  # harvest_rate * dt
    assert t.spice == 450
    print("[PASS] test_harvester")


def test_map_json():
    gm = GameMap()
    gm.generate_default()
    gm.save_to_json("/tmp/test_map.json")
    gm2 = GameMap()
    gm2.load_from_json("/tmp/test_map.json")
    assert gm2.width == gm.width
    assert gm2.height == gm.height
    assert len(gm2.starting_positions) == 2
    # Spot check a tile
    assert gm2.tiles[5][5].terrain == gm.tiles[5][5].terrain
    print("[PASS] test_map_json")


def test_building_footprint():
    """Buildings expose one Y-flipped footprint convention shared by rendering,
    picking and combat. Regression for the three-disagreeing-conventions bug."""
    from settings import TILE_SIZE, MAP_HEIGHT
    b = Building.create("construction_yard", 0, 5, 5)  # 3x3 at tile (5,5)
    assert b.world_left == 5 * TILE_SIZE                        # 160
    assert b.world_bottom == (MAP_HEIGHT - 5 - 3) * TILE_SIZE   # (64-5-3)*32 = 1792
    assert b.pixel_x == b.world_left + (b.size_w * TILE_SIZE) / 2     # 208
    assert b.pixel_y == b.world_bottom + (b.size_h * TILE_SIZE) / 2   # 1840
    # create() seeds the Entity world position from the footprint center
    assert b.x == b.pixel_x and b.y == b.pixel_y
    print("[PASS] test_building_footprint")


def test_harvester_deposit_credits():
    """A full harvester parked at its refinery deposits and credits go up.
    Regression for the coordinate bug that made deposits never fire."""
    from systems.movement_system import MovementSystem
    from systems.resource_system import ResourceSystem
    from entities.unit import UnitState
    from settings import TILE_SIZE, BUILDING_STATS
    gm = GameMap(); gm.generate_default()
    gs = GameState()
    gs.players[0] = Player(player_id=0, house="atreides", credits=0)
    ref = Building.create("refinery", 0, 10, 10)
    rid = gs.add_entity(ref)
    s = BUILDING_STATS["refinery"]["size_tiles"]
    gm.place_building_tiles(10, 10, s[0], s[1], rid)
    # Full harvester sitting on the refinery footprint centre (well within range)
    h = Harvester(owner_id=0, x=ref.pixel_x, y=ref.pixel_y)
    h.spice_carried = h.capacity
    h.state = UnitState.RETURNING
    h.target_refinery_id = rid
    gs.add_entity(h)
    assert h.distance_to_point(ref.x, ref.y) < TILE_SIZE * 4  # deposit threshold
    before = gs.players[0].credits
    rs = ResourceSystem(gs, gm, MovementSystem(gm))
    rs.update(0.1)
    assert gs.players[0].credits == before + 1500, gs.players[0].credits
    assert h.spice_carried == 0
    print("[PASS] test_harvester_deposit_credits")


def test_turret_acquires_and_fires():
    """A Gun Turret auto-fires at an enemy unit in range, producing a projectile
    aimed at that unit (buildings can now participate in combat)."""
    from systems.movement_system import MovementSystem
    from systems.combat_system import CombatSystem
    from entities.unit import UnitState
    from settings import TILE_SIZE
    gm = GameMap(); gm._init_empty()
    gs = GameState()
    gs.players[0] = Player(player_id=0, house="atreides")
    gs.players[1] = Player(player_id=1, house="harkonnen")
    turret = Building.create("gun_turret", 0, 10, 10)
    tid = gs.add_entity(turret)
    assert turret.is_combat and turret.attack_range_pixels == 5 * TILE_SIZE
    enemy = Soldier(owner_id=1, x=turret.pixel_x + 50, y=turret.pixel_y)
    enemy.state = UnitState.IDLE
    eid = gs.add_entity(enemy)
    cs = CombatSystem(gs, MovementSystem(gm))
    cs.update(0.1, gs.entities)
    fired = [p for p in cs.projectiles if p.owner_id == 0 and p.target_id == eid]
    assert fired, "turret should have fired at the enemy unit"
    print("[PASS] test_turret_acquires_and_fires")


def test_heavy_factory_produces_mcv():
    """The Heavy Factory can build an MCV (enabling the deploy-a-new-base loop
    that was previously dead content because nothing produced an MCV)."""
    from systems.production_system import ProductionSystem
    from settings import BUILDING_STATS
    gm = GameMap(); gm.generate_default()
    gs = GameState()
    gs.players[0] = Player(player_id=0, house="atreides", credits=5000)
    hf = Building.create("heavy_factory", 0, 12, 12)
    hid = gs.add_entity(hf)
    s = BUILDING_STATS["heavy_factory"]["size_tiles"]
    gm.place_building_tiles(12, 12, s[0], s[1], hid)
    assert "mcv" in hf.get_producible()
    hf.queue_production("mcv")
    ps = ProductionSystem(gs, gm)
    for _ in range(20):  # start (charge) + advance past the 15s build time
        ps.update(1.0)
    mcvs = [e for e in gs.entities.values() if isinstance(e, MCV) and e.owner_id == 0]
    assert mcvs, "heavy factory should have produced an MCV"
    print("[PASS] test_heavy_factory_produces_mcv")


if __name__ == "__main__":
    test_pathfinding()
    test_pathfinding_no_path()
    test_game_state()
    test_player_credits()
    test_tile_harvest()
    test_building_create()
    test_soldier_combat()
    test_harvester()
    test_map_json()
    test_building_footprint()
    test_harvester_deposit_credits()
    test_turret_acquires_and_fires()
    test_heavy_factory_produces_mcv()
    print("\n=== ALL TESTS PASSED ===")
