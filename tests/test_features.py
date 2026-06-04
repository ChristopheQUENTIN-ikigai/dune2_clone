#!/usr/bin/env python3
"""Tests for the new features: construction progress, new units, flying
movement, AI squadron waves, and save/load of the new content."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.game_state import GameState
from core.player import Player
from core.command import Command, CommandType
from map.game_map import GameMap
from entities.building import Building
from entities.unit import Unit, UnitState, tile_to_world
from entities.vehicle import Vehicle, make_unit
from entities.soldier import Soldier
from systems.simulation import Simulation
from systems.production_system import ProductionSystem
from systems.movement_system import MovementSystem
from ai.ai_controller import AIController, is_combat_unit
from save import save_game, load_game
from settings import BUILDING_STATS, UNIT_STATS, TICK_RATE


def _new_world():
    gm = GameMap()
    gm.generate_default()
    gs = GameState()
    gs.players[0] = Player(0, "atreides", False, 50000)
    gs.players[1] = Player(1, "harkonnen", True, 50000)
    sim = Simulation(gs, gm)
    return gs, gm, sim


def _place_built_cy(gs, gm, pid, tx, ty, btype="construction_yard"):
    b = Building.create(btype, pid, tx, ty, built=True)
    eid = gs.add_entity(b)
    s = BUILDING_STATS[btype]["size_tiles"]
    gm.place_building_tiles(tx, ty, s[0], s[1], eid)
    return b


def test_construction_progress():
    gs, gm, sim = _new_world()
    p = gs.players[0]
    # Find a buildable spot
    spot = None
    for ty in range(2, 12):
        for tx in range(2, 12):
            if gm.can_place_building(tx, ty, 2, 2):
                spot = (tx, ty); break
        if spot: break
    assert spot, "need a buildable tile"
    pp0 = p.power_produced
    ok = sim.production.start_building_placement(0, "solar_plant", spot[0], spot[1])
    assert ok, "placement should succeed"
    b = [e for e in gs.entities.values() if isinstance(e, Building)][0]
    assert not b.built, "building starts under construction"
    assert b.construction_progress < 1.0
    assert p.power_produced == pp0, "power not applied while constructing"
    # Advance ~ build_time seconds
    bt = BUILDING_STATS["solar_plant"]["build_time"]
    steps = int(bt * TICK_RATE) + 5
    for _ in range(steps):
        sim.production.update(1.0 / TICK_RATE)
    assert b.built, "building completes after build_time"
    assert b.construction_progress == 1.0
    assert p.power_produced == pp0 + 50, "solar power applied on completion"
    print("[PASS] test_construction_progress")


def test_cannot_produce_while_constructing():
    gs, gm, sim = _new_world()
    # barracks under construction
    ok = sim.production.start_building_placement(0, "barracks", 3, 3) or \
         sim.production.start_building_placement(0, "barracks", 5, 5)
    b = [e for e in gs.entities.values() if isinstance(e, Building)][0]
    assert not b.built
    assert sim.production.request_unit_production(b, "soldier") is False
    print("[PASS] test_cannot_produce_while_constructing")


def test_new_units_produced():
    gs, gm, sim = _new_world()
    hf = _place_built_cy(gs, gm, 0, 4, 4, "heavy_factory")
    assert sim.production.request_unit_production(hf, "tank") is True
    bt = UNIT_STATS["tank"]["build_time"]
    for _ in range(int(bt * TICK_RATE) + 5):
        sim.production.update(1.0 / TICK_RATE)
    tanks = [e for e in gs.entities.values()
             if isinstance(e, Unit) and e.unit_type == "tank"]
    assert len(tanks) == 1, "tank should spawn"
    assert tanks[0].attack_damage == UNIT_STATS["tank"]["attack_damage"]
    print("[PASS] test_new_units_produced")


def test_all_unit_types_constructible():
    for t in UNIT_STATS:
        u = make_unit(t, 0, 100, 100)
        assert u is not None, f"{t} should build"
        assert u.unit_type == t
    print("[PASS] test_all_unit_types_constructible")


def test_flying_unit_ignores_terrain():
    gs, gm, sim = _new_world()
    heli = make_unit("helicopter", 0, *tile_to_world(5, 5))
    gs.add_entity(heli)
    assert heli.flying is True
    mv = MovementSystem(gm)
    # Target a mountain tile (impassable for ground) - heli should still path
    goal = None
    for ty in range(gm.height):
        for tx in range(gm.width):
            if gm.tiles[ty][tx].terrain == "mountain":
                goal = (tx, ty); break
        if goal: break
    assert goal, "map should have a mountain"
    mv.issue_move(heli, goal[0], goal[1])
    assert heli.path == [goal], "flying unit flies straight to goal (single hop)"
    # Simulate until it arrives
    for _ in range(2000):
        if not heli.is_moving:
            break
        heli.update_movement(1.0 / TICK_RATE)
    assert heli.tile_x == goal[0] and heli.tile_y == goal[1], "heli reaches mountain tile"
    print("[PASS] test_flying_unit_ignores_terrain")


def test_splash_projectile():
    from systems.combat_system import CombatSystem, Projectile
    gs, gm, sim = _new_world()
    # two enemy soldiers close together
    a = Soldier(owner_id=1, x=500, y=500); gs.add_entity(a)
    b = Soldier(owner_id=1, x=515, y=500); gs.add_entity(b)
    cs = sim.combat
    cs.projectiles.append(Projectile(x=500, y=500, target_x=500, target_y=500,
                                     damage=40, target_id=a.entity_id, owner_id=0,
                                     splash_radius=40))
    ha, hb = a.health, b.health
    cs.update(1.0 / TICK_RATE, gs.entities)
    assert a.health < ha, "direct target damaged"
    assert b.health < hb, "splash hit nearby enemy"
    print("[PASS] test_splash_projectile")


def test_ai_launches_coordinated_wave():
    gs, gm, sim = _new_world()
    # AI base + enemy base
    _place_built_cy(gs, gm, 1, 56, 56, "construction_yard")
    enemy_cy = _place_built_cy(gs, gm, 0, 5, 5, "construction_yard")
    ai = AIController(gs, gm, 1)
    # Give the AI a full squad of tanks near its base
    tank_ids = []
    for i in range(6):
        t = make_unit("tank", 1, *tile_to_world(54 + i % 3, 58))
        t.state = UnitState.IDLE
        tank_ids.append(gs.add_entity(t))
    ai._manage_squadrons()
    assert len(ai.waves) >= 1, "a wave should launch when squad is full"
    wave = ai.waves[0]
    assert wave["target"] == enemy_cy.entity_id, "wave targets enemy construction yard"
    # An ATTACK command for the squad should be queued
    atk = [c for c in gs.command_queue if c.command_type == CommandType.ATTACK]
    assert atk, "attack command queued for the wave"
    assert set(tank_ids) & set(atk[-1].entity_ids), "wave units are commanded together"
    # Execute it and confirm units are now attacking as a group
    sim._tick()
    attacking = [gs.entities[i] for i in tank_ids if i in gs.entities]
    assert any(u.state == UnitState.ATTACKING for u in attacking), "units engage together"
    print("[PASS] test_ai_launches_coordinated_wave")


def test_ai_defends_base():
    gs, gm, sim = _new_world()
    cy = _place_built_cy(gs, gm, 1, 56, 56, "construction_yard")
    ai = AIController(gs, gm, 1)
    # Small squad (below wave threshold) so it should defend, not attack
    defenders = []
    for i in range(2):
        t = make_unit("trike", 1, *tile_to_world(54 + i, 58))
        t.state = UnitState.IDLE
        defenders.append(gs.add_entity(t))
    # An enemy unit right next to the AI base
    intruder = Soldier(owner_id=0, x=0, y=0)
    intruder.x, intruder.y = tile_to_world(57, 57)
    iid = gs.add_entity(intruder)
    ai._manage_squadrons()
    atk = [c for c in gs.command_queue if c.command_type == CommandType.ATTACK]
    assert atk, "defenders should be ordered to attack the intruder"
    assert atk[-1].target_entity_id == iid
    print("[PASS] test_ai_defends_base")


def test_save_load_new_content():
    gs, gm, sim = _new_world()
    _place_built_cy(gs, gm, 0, 5, 5, "construction_yard")
    # a tank and an under-construction airfield
    tank = make_unit("tank", 0, *tile_to_world(8, 8))
    gs.add_entity(tank)
    sim.production.start_building_placement(0, "light_factory", 9, 9) or \
        sim.production.start_building_placement(0, "light_factory", 11, 11)
    constructing = [e for e in gs.entities.values()
                    if isinstance(e, Building) and not e.built]
    assert constructing, "should have an under-construction building"
    cid = constructing[0].entity_id
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "s.json")
        save_game(gs, gm, path)
        gs2, tiles = load_game(path)
    assert gs2 is not None
    tanks = [e for e in gs2.entities.values()
             if isinstance(e, Unit) and e.unit_type == "tank"]
    assert len(tanks) == 1, "tank survives save/load"
    b2 = gs2.entities.get(cid)
    assert b2 is not None and not b2.built, "construction state restored"
    assert 0.0 <= b2.construction_progress < 1.0
    print("[PASS] test_save_load_new_content")


if __name__ == "__main__":
    test_construction_progress()
    test_cannot_produce_while_constructing()
    test_new_units_produced()
    test_all_unit_types_constructible()
    test_flying_unit_ignores_terrain()
    test_splash_projectile()
    test_ai_launches_coordinated_wave()
    test_ai_defends_base()
    test_save_load_new_content()
    print("\n=== ALL FEATURE TESTS PASSED ===")
