"""
Save/Load system — serializes full game state to/from JSON.
"""
import json
import os
from pathlib import Path
from core.game_state import GameState
from core.player import Player
from entities.building import Building
from entities.soldier import Soldier
from entities.harvester import Harvester
from entities.mcv import MCV
from entities.unit import Unit, UnitState, tile_to_world
from settings import SAVES_PATH, BUILDING_STATS, TILE_SIZE, MAP_HEIGHT


def ensure_saves_dir():
    SAVES_PATH.mkdir(parents=True, exist_ok=True)


def save_game(game_state: GameState, game_map, filepath: str = None):
    """Save entire game state to JSON."""
    ensure_saves_dir()
    if filepath is None:
        filepath = str(SAVES_PATH / "quicksave.json")

    data = {
        "tick": game_state.tick,
        "next_entity_id": game_state.next_entity_id,
        "players": {},
        "entities": [],
        "map_tiles": [],
    }

    # Players
    for pid, p in game_state.players.items():
        data["players"][str(pid)] = {
            "player_id": p.player_id,
            "house": p.house,
            "is_ai": p.is_ai,
            "credits": p.credits,
            "power_produced": p.power_produced,
            "power_consumed": p.power_consumed,
        }

    # Entities
    for eid, e in game_state.entities.items():
        ed = {
            "entity_id": e.entity_id,
            "owner_id": e.owner_id,
            "health": e.health,
            "max_health": e.max_health,
            "x": e.x,
            "y": e.y,
        }
        if isinstance(e, Building):
            ed["type"] = "building"
            ed["building_type"] = e.building_type
            ed["tile_x"] = e.tile_x
            ed["tile_y"] = e.tile_y
            ed["producing"] = e.producing
            ed["production_timer"] = e.production_timer
            ed["production_total_time"] = e.production_total_time
            ed["production_queue"] = list(e.production_queue)
            ed["built"] = e.built
            ed["construction_timer"] = e.construction_timer
            ed["construction_total_time"] = e.construction_total_time
        elif isinstance(e, Harvester):
            ed["type"] = "harvester"
            ed["unit_type"] = e.unit_type
            ed["spice_carried"] = e.spice_carried
            ed["state"] = e.state.value
            ed["target_refinery_id"] = e.target_refinery_id
        elif isinstance(e, MCV):
            ed["type"] = "mcv"
            ed["state"] = e.state.value
        elif isinstance(e, Soldier):
            ed["type"] = "soldier"
            ed["state"] = e.state.value
        elif isinstance(e, Unit):
            ed["type"] = "unit"
            ed["unit_type"] = e.unit_type
            ed["state"] = e.state.value
            ed["target_entity_id"] = e.target_entity_id
        data["entities"].append(ed)

    # Map non-default tiles
    for y in range(game_map.height):
        for x in range(game_map.width):
            t = game_map.tiles[y][x]
            if t.terrain != "sand" or t.spice > 0:
                data["map_tiles"].append({
                    "x": x, "y": y,
                    "terrain": t.terrain,
                    "spice": t.spice,
                })

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=1)
    return filepath


def load_game(filepath: str = None):
    """Load game state from JSON. Returns (game_state, needs_map_rebuild)."""
    if filepath is None:
        filepath = str(SAVES_PATH / "quicksave.json")

    if not os.path.exists(filepath):
        return None, None

    with open(filepath, 'r') as f:
        data = json.load(f)

    gs = GameState()
    gs.tick = data["tick"]
    gs.next_entity_id = data["next_entity_id"]

    # Players
    for pid_str, pd in data["players"].items():
        pid = int(pid_str)
        gs.players[pid] = Player(
            player_id=pd["player_id"],
            house=pd["house"],
            is_ai=pd["is_ai"],
            credits=pd["credits"],
        )
        gs.players[pid].power_produced = pd["power_produced"]
        gs.players[pid].power_consumed = pd["power_consumed"]

    # Entities
    for ed in data["entities"]:
        etype = ed["type"]
        eid = ed["entity_id"]
        owner = ed["owner_id"]

        if etype == "building":
            built = ed.get("built", True)
            e = Building.create(ed["building_type"], owner, ed["tile_x"], ed["tile_y"], built=built)
            e.entity_id = eid
            e.health = ed["health"]
            e.max_health = ed["max_health"]
            e.producing = ed.get("producing")
            e.production_timer = ed.get("production_timer", 0)
            e.production_total_time = ed.get("production_total_time", 0)
            e.production_queue = ed.get("production_queue", [])
            e.built = built
            e.construction_timer = ed.get("construction_timer", 0.0)
            e.construction_total_time = ed.get("construction_total_time", 0.0)
            e.build_progress = e.construction_progress
        elif etype == "harvester":
            e = Harvester(entity_id=eid, owner_id=owner, x=ed["x"], y=ed["y"])
            e.health = ed["health"]
            e.max_health = ed["max_health"]
            e.spice_carried = ed.get("spice_carried", 0)
            e.target_refinery_id = ed.get("target_refinery_id", -1)
            e.state = UnitState(ed.get("state", "idle"))
        elif etype == "mcv":
            e = MCV(entity_id=eid, owner_id=owner, x=ed["x"], y=ed["y"])
            e.health = ed["health"]
            e.state = UnitState(ed.get("state", "idle"))
        elif etype == "soldier":
            e = Soldier(entity_id=eid, owner_id=owner, x=ed["x"], y=ed["y"])
            e.health = ed["health"]
            e.state = UnitState(ed.get("state", "idle"))
        elif etype == "unit":
            from entities.vehicle import make_unit
            e = make_unit(ed.get("unit_type", "trike"), owner, ed["x"], ed["y"])
            if e is None:
                continue
            e.entity_id = eid
            e.health = ed["health"]
            e.state = UnitState(ed.get("state", "idle"))
            e.target_entity_id = ed.get("target_entity_id")
        else:
            continue

        gs.entities[eid] = e
        if owner in gs.players:
            gs.players[owner].entity_ids.append(eid)

    return gs, data.get("map_tiles", [])


def get_quicksave_path():
    return str(SAVES_PATH / "quicksave.json")


def timestamped_save_path():
    import time
    ensure_saves_dir()
    return str(SAVES_PATH / time.strftime("save_%Y%m%d_%H%M%S.json"))


def quicksave_exists():
    return os.path.exists(get_quicksave_path())
