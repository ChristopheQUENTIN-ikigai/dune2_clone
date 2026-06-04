"""
Combat system with projectile visuals. All positions in world coords.
"""
import math
from dataclasses import dataclass
from entities.unit import Unit, UnitState
from entities.building import Building
from settings import TILE_SIZE


@dataclass
class Projectile:
    x: float
    y: float
    target_x: float
    target_y: float
    speed: float = 300.0
    damage: int = 0
    target_id: int = 0
    owner_id: int = 0
    splash_radius: float = 0.0
    alive: bool = True

    def update(self, dt):
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dist = math.hypot(dx, dy)
        if dist < 4.0:
            self.alive = False
            return True
        move = self.speed * dt
        if move >= dist:
            self.x, self.y = self.target_x, self.target_y
            self.alive = False
            return True
        self.x += (dx / dist) * move
        self.y += (dy / dist) * move
        return False


class CombatSystem:
    def __init__(self, game_state, movement_system):
        self.game_state = game_state
        self.movement_system = movement_system
        self.projectiles = []
        self.tick_dt = 0.0

    def issue_attack(self, attacker, target_id):
        attacker.target_entity_id = target_id
        attacker.state = UnitState.ATTACKING

    def _get_entity_world_pos(self, entity):
        """Get world-space center for any entity.

        Buildings expose their footprint center via pixel_x/pixel_y (Y-flipped,
        matching rendering and picking), so combat aims at the same spot the
        player sees.
        """
        if isinstance(entity, Building):
            return entity.pixel_x, entity.pixel_y
        return entity.x, entity.y

    def _distance_between(self, e1, e2):
        x1, y1 = self._get_entity_world_pos(e1)
        x2, y2 = self._get_entity_world_pos(e2)
        return math.hypot(x1 - x2, y1 - y2)

    def update(self, dt, entities):
        dead_ids = []
        self.tick_dt = dt

        for entity in list(entities.values()):
            if not isinstance(entity, Unit) or not entity.alive or entity.attack_damage <= 0:
                continue
            entity.update_attack(dt)

            if entity.state == UnitState.ATTACKING and entity.target_entity_id:
                target = entities.get(entity.target_entity_id)
                if not target or not target.alive:
                    entity.target_entity_id = None
                    entity.state = UnitState.IDLE
                    entity.path = []
                    continue

                dist = self._distance_between(entity, target)
                if dist <= entity.attack_range_pixels:
                    entity.path = []
                    if entity.can_attack():
                        damage = entity.do_attack()
                        tx, ty = self._get_entity_world_pos(target)
                        self.projectiles.append(Projectile(
                            x=entity.x, y=entity.y,
                            target_x=tx, target_y=ty,
                            damage=damage, target_id=target.entity_id,
                            owner_id=entity.owner_id,
                            splash_radius=getattr(entity, "splash", 0.0) * TILE_SIZE))
                else:
                    if not entity.is_moving:
                        if isinstance(target, Building):
                            ttx = target.tile_x + target.size_w // 2
                            tty = target.tile_y + target.size_h
                        else:
                            ttx, tty = target.tile_x, target.tile_y
                        self.movement_system.issue_move(entity, ttx, tty, preserve_state="attack")
                        entity.state = UnitState.ATTACKING

            elif entity.state == UnitState.IDLE:
                self._auto_attack(entity, entities)

        # Defensive buildings (e.g. Gun Turret) acquire and fire at enemies in range.
        for entity in list(entities.values()):
            if (isinstance(entity, Building) and entity.alive
                    and entity.built and entity.is_combat):
                self._update_building_combat(entity, entities)

        for proj in self.projectiles:
            if not proj.alive:
                continue
            if proj.update(dt):
                target = entities.get(proj.target_id)
                impact_x, impact_y = proj.target_x, proj.target_y
                if target and target.alive:
                    target.take_damage(proj.damage)
                    impact_x, impact_y = self._get_entity_world_pos(target)
                    if not target.alive:
                        dead_ids.append(target.entity_id)
                # Splash: rockets/bombs also damage nearby enemies (half damage).
                if proj.splash_radius > 0:
                    for other in list(entities.values()):
                        if (not other.alive or other.owner_id == proj.owner_id
                                or other.entity_id == proj.target_id):
                            continue
                        ox, oy = self._get_entity_world_pos(other)
                        if math.hypot(ox - impact_x, oy - impact_y) <= proj.splash_radius:
                            other.take_damage(max(1, proj.damage // 2))
                            if not other.alive:
                                dead_ids.append(other.entity_id)

        self.projectiles = [p for p in self.projectiles if p.alive]
        for eid in set(dead_ids):
            self.game_state.remove_entity(eid)

    def _auto_attack(self, unit, entities):
        sight = unit.attack_range_pixels * 3
        nearest, nd = None, float('inf')
        for other in entities.values():
            if not other.alive or other.owner_id == unit.owner_id:
                continue
            d = self._distance_between(unit, other)
            if d < sight and d < nd:
                nearest, nd = other, d
        if nearest:
            unit.target_entity_id = nearest.entity_id
            unit.state = UnitState.ATTACKING

    def _update_building_combat(self, turret, entities):
        """Static defensive structure: hold position, fire at the nearest enemy
        within range. Re-acquires every tick so it always engages the closest
        threat and never chases."""
        turret.update_attack(self.tick_dt)
        rng = turret.attack_range_pixels

        target = entities.get(turret.target_entity_id) if turret.target_entity_id else None
        if (not target or not target.alive
                or target.owner_id == turret.owner_id
                or self._distance_between(turret, target) > rng):
            target = None
            nearest, nd = None, float('inf')
            for other in entities.values():
                if not other.alive or other.owner_id == turret.owner_id:
                    continue
                if isinstance(other, Building):
                    continue  # turrets target units, not enemy structures
                d = self._distance_between(turret, other)
                if d <= rng and d < nd:
                    nearest, nd = other, d
            target = nearest
            turret.target_entity_id = target.entity_id if target else None

        if target and turret.can_attack():
            damage = turret.do_attack()
            tx, ty = self._get_entity_world_pos(target)
            bx, by = self._get_entity_world_pos(turret)
            self.projectiles.append(Projectile(
                x=bx, y=by, target_x=tx, target_y=ty,
                damage=damage, target_id=target.entity_id,
                owner_id=turret.owner_id, speed=420.0))
