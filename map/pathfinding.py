"""
A* pathfinding on the tile grid.
"""
import heapq
from typing import Optional


def heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Manhattan distance heuristic."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(game_map, start: tuple[int, int], goal: tuple[int, int],
          max_iterations: int = 2000) -> Optional[list[tuple[int, int]]]:
    """
    Find path from start to goal on the game map.
    Returns list of (tx, ty) tile coordinates, or None if no path found.
    """
    if not game_map.is_passable(goal[0], goal[1]):
        # Try to find nearest passable tile to goal
        goal = _nearest_passable(game_map, goal)
        if goal is None:
            return None

    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from: dict[tuple, tuple] = {}
    g_score: dict[tuple, float] = {start: 0}
    f_score: dict[tuple, float] = {start: heuristic(start, goal)}
    closed_set: set[tuple] = set()
    iterations = 0

    while open_set and iterations < max_iterations:
        iterations += 1
        current_f, current = heapq.heappop(open_set)

        if current == goal:
            return _reconstruct_path(came_from, current)

        if current in closed_set:
            continue
        closed_set.add(current)

        for neighbor in _get_neighbors(game_map, current):
            if neighbor in closed_set:
                continue

            # Diagonal movement costs more
            dx = abs(neighbor[0] - current[0])
            dy = abs(neighbor[1] - current[1])
            move_cost = 1.414 if dx + dy == 2 else 1.0

            tentative_g = g_score[current] + move_cost

            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + heuristic(neighbor, goal)
                f_score[neighbor] = f
                heapq.heappush(open_set, (f, neighbor))

    return None  # No path found


def _get_neighbors(game_map, pos: tuple[int, int]) -> list[tuple[int, int]]:
    """Get passable neighbors (8-directional)."""
    x, y = pos
    neighbors = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if game_map.is_passable(nx, ny):
                # For diagonal movement, check that both cardinal directions are passable
                if dx != 0 and dy != 0:
                    if not game_map.is_passable(x + dx, y) or not game_map.is_passable(x, y + dy):
                        continue
                neighbors.append((nx, ny))
    return neighbors


def _nearest_passable(game_map, pos: tuple[int, int],
                       max_range: int = 10) -> Optional[tuple[int, int]]:
    """Find nearest passable tile to a given position."""
    for r in range(1, max_range + 1):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if abs(dx) != r and abs(dy) != r:
                    continue
                nx, ny = pos[0] + dx, pos[1] + dy
                if game_map.is_passable(nx, ny):
                    return (nx, ny)
    return None


def _reconstruct_path(came_from: dict, current: tuple) -> list[tuple[int, int]]:
    """Reconstruct path from came_from map."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
