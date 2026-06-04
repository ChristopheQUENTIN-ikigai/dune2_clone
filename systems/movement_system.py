"""
Movement system — A* pathfinding, waypoint queue, building avoidance.
"""
from entities.unit import Unit, UnitState
from map.pathfinding import astar


class MovementSystem:
    def __init__(self, game_map):
        self.game_map = game_map

    def issue_move(self, unit, target_tx, target_ty, preserve_state=""):
        start = (unit.tile_x, unit.tile_y)
        goal = (target_tx, target_ty)
        if start == goal:
            if not preserve_state:
                unit.stop()
            return
        # Air units ignore terrain and pathfinding — they fly straight to the
        # goal in a single hop. Ground units use A* around obstacles.
        if getattr(unit, "flying", False):
            unit.set_path([goal], preserve_state=preserve_state)
            return
        path = astar(self.game_map, start, goal)
        if path:
            unit.set_path(path, preserve_state=preserve_state)
        else:
            if not preserve_state:
                unit.stop()

    def issue_waypoint_move(self, unit, target_tx, target_ty):
        if unit.is_moving or unit.state == UnitState.MOVING:
            unit.add_waypoint(target_tx, target_ty)
        else:
            self.issue_move(unit, target_tx, target_ty)

    def update(self, dt, entities):
        for entity in entities.values():
            if isinstance(entity, Unit) and entity.alive and entity.is_moving:
                reached = entity.update_movement(dt)
                if reached and entity.waypoint_queue:
                    next_wp = entity.waypoint_queue.pop(0)
                    self.issue_move(entity, next_wp[0], next_wp[1])
