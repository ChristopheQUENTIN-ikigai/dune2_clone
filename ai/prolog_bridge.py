"""
Prolog bridge — asserts game facts into SWI-Prolog via Janus,
queries for AI decisions. Falls back to simple Python AI if
Janus is not available.
"""
import os
from pathlib import Path
from typing import Optional

# Try to import janus
JANUS_AVAILABLE = False
try:
    import janus_swi as janus
    JANUS_AVAILABLE = True
except ImportError:
    pass


class PrologBridge:
    """Interface between Python game state and Prolog AI."""

    def __init__(self, prolog_file: str = None):
        self.active = False
        if prolog_file is None:
            prolog_file = str(Path(__file__).parent / "strategy.pl")
        self.prolog_file = prolog_file

        if JANUS_AVAILABLE:
            try:
                janus.consult(self.prolog_file)
                self.active = True
                print("[AI] Prolog engine loaded successfully.")
            except Exception as e:
                print(f"[AI] Prolog load failed: {e}. Using fallback AI.")
        else:
            print("[AI] Janus not available. Using fallback Python AI.")

    def assert_game_state(self, game_state, player_id: int, game_map):
        """Push current game state into Prolog as facts."""
        if not self.active:
            return

        try:
            # Retract all dynamic facts
            for pred in ["my_credits", "my_power", "my_building", "my_unit",
                        "enemy_building", "enemy_unit", "spice_field",
                        "game_tick", "my_building_id", "my_unit_id"]:
                janus.query_once(f"retractall({pred}(_))" if pred in ["my_credits", "game_tick"]
                                else f"retractall({pred}(_,_,_,_))" if pred.endswith("unit") or pred.endswith("building")
                                else f"retractall({pred}(_,_))" if pred in ["my_power", "my_building_id", "my_unit_id"]
                                else f"retractall({pred}(_,_,_))")

            # Assert tick
            janus.query_once(f"assert(game_tick({game_state.tick}))")

            player = game_state.players[player_id]
            enemy_id = [p for p in game_state.players if p != player_id][0]

            # Credits and power
            janus.query_once(f"assert(my_credits({int(player.credits)}))")
            janus.query_once(f"assert(my_power({player.power_consumed},{player.power_produced}))")

            # My buildings
            from entities.building import Building
            from entities.unit import Unit
            for eid in player.entity_ids:
                entity = game_state.entities.get(eid)
                if not entity or not entity.alive:
                    continue
                if isinstance(entity, Building):
                    janus.query_once(
                        f"assert(my_building({entity.building_type},{entity.tile_x},{entity.tile_y},{entity.health}))"
                    )
                    janus.query_once(
                        f"assert(my_building_id({entity.building_type},{eid}))"
                    )
                elif isinstance(entity, Unit):
                    tx, ty = entity.tile_x, entity.tile_y
                    janus.query_once(
                        f"assert(my_unit({entity.unit_type},{tx},{ty},{entity.health}))"
                    )
                    janus.query_once(
                        f"assert(my_unit_id({entity.unit_type},{eid}))"
                    )

            # Enemy entities
            for eid in game_state.players[enemy_id].entity_ids:
                entity = game_state.entities.get(eid)
                if not entity or not entity.alive:
                    continue
                if isinstance(entity, Building):
                    janus.query_once(
                        f"assert(enemy_building({entity.building_type},{entity.tile_x},{entity.tile_y},{entity.health}))"
                    )
                elif isinstance(entity, Unit):
                    tx, ty = entity.tile_x, entity.tile_y
                    janus.query_once(
                        f"assert(enemy_unit({entity.unit_type},{tx},{ty},{entity.health}))"
                    )

            # Spice fields
            for y in range(game_map.height):
                for x in range(game_map.width):
                    tile = game_map.tiles[y][x]
                    if tile.has_spice:
                        janus.query_once(
                            f"assert(spice_field({x},{y},{int(tile.spice)}))"
                        )

        except Exception as e:
            print(f"[AI] Error asserting state: {e}")

    def query_decisions(self) -> list[tuple[str, str]]:
        """Query Prolog for AI decisions. Returns list of (action, target)."""
        if not self.active:
            return []

        decisions = []
        try:
            # Get all decisions
            results = list(janus.query("decision(Action, Target)"))
            for r in results:
                decisions.append((str(r["Action"]), str(r["Target"])))

            # Get best attack target
            target_results = list(janus.query("best_target(Type, X, Y)"))
            for r in target_results:
                decisions.append(("target", f"{r['Type']}_{r['X']}_{r['Y']}"))

            # Get strategy
            strat_results = list(janus.query("recommend_strategy(S)"))
            if strat_results:
                decisions.append(("strategy", str(strat_results[0]["S"])))

        except Exception as e:
            print(f"[AI] Query error: {e}")

        return decisions

    def query_strategy(self) -> str:
        """Get current strategic recommendation."""
        if not self.active:
            return "military"
        try:
            results = list(janus.query("recommend_strategy(S)"))
            if results:
                return str(results[0]["S"])
        except Exception:
            pass
        return "military"
