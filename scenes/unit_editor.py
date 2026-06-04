"""
Unit Editor — tweak unit stats (cost, health, speed, damage, range, cooldown,
size, flying) and save them back to config.json. Saved changes also update the
in-memory stats so they take effect for units built afterwards in this session.

Left column: pick a unit. Right column: +/- steppers for each stat, plus a
flying toggle. Buttons: Save, Reload (discard unsaved edits), Menu.
"""
import json
import copy
import arcade
from scenes.scene_manager import Scene
from ui.widgets import draw_button, point_in
import settings
from settings import UNIT_STATS, HOUSES, CONFIG_PATH

# (label, key, step, kind) — kind: "int", "float", "bool"
FIELDS = [
    ("Cost",           "cost",            25,  "int"),
    ("Build time (s)", "build_time",      0.5, "float"),
    ("Health",         "health",          10,  "int"),
    ("Speed",          "speed",           5,   "int"),
    ("Attack damage",  "attack_damage",   1,   "int"),
    ("Attack range",   "attack_range",    1,   "int"),
    ("Attack cooldown","attack_cooldown", 0.1, "float"),
    ("Size",           "size",            1,   "int"),
    ("Flying",         "flying",          0,   "bool"),
]


class UnitEditorScene(Scene):
    LIST_W = 220

    def __init__(self, window):
        super().__init__(window)
        # Working copy we edit; written to disk + in-memory on Save.
        self.units = copy.deepcopy(dict(UNIT_STATS))
        self.order = list(self.units.keys())
        self.selected = self.order[0] if self.order else None
        self.mouse_x = self.mouse_y = 0
        self.notification = ""
        self.notif_timer = 0.0
        self.dirty = False
        self._buttons = []
        self._list_rects = []

    def on_show(self):
        arcade.set_background_color((20, 17, 12))

    def _notify(self, m):
        self.notification = m
        self.notif_timer = 2.5

    # ----- update -----
    def on_update(self, dt):
        if self.notif_timer > 0:
            self.notif_timer -= dt

    # ----- drawing -----
    def on_draw(self):
        self.window.clear()
        w, h = self.window.width, self.window.height
        arcade.draw_text("UNIT EDITOR", w / 2, h - 34, (225, 195, 105), 22,
                         anchor_x="center", font_name="Courier New", bold=True)
        arcade.draw_text("Edit unit stats - saved to config.json (applies to new units)",
                         w / 2, h - 58, (160, 145, 105), 11, anchor_x="center",
                         font_name="Courier New")
        self._draw_list()
        self._draw_editor()
        if self.notif_timer > 0:
            arcade.draw_text(self.notification, w / 2, 18, (255, 240, 140), 14,
                             anchor_x="center", font_name="Courier New")

    def _draw_list(self):
        h = self.window.height
        x0 = 16
        arcade.draw_lrbt_rectangle_filled(x0 - 6, x0 + self.LIST_W, 70, h - 80, (28, 24, 17, 235))
        arcade.draw_lrbt_rectangle_outline(x0 - 6, x0 + self.LIST_W, 70, h - 80, (80, 70, 50), 1)
        self._list_rects = []
        y = h - 96
        for t in self.order:
            sel = (t == self.selected)
            name = self.units[t].get("name", t)
            cat = self.units[t].get("category", "")
            bg = (74, 64, 44) if sel else (44, 38, 27)
            arcade.draw_lrbt_rectangle_filled(x0, x0 + self.LIST_W - 12, y, y + 30, bg)
            arcade.draw_lrbt_rectangle_outline(x0, x0 + self.LIST_W - 12, y, y + 30,
                                               (220, 195, 95) if sel else (70, 62, 46),
                                               2 if sel else 1)
            arcade.draw_text(name, x0 + 10, y + 10, (240, 220, 140) if sel else (205, 188, 128),
                             13, font_name="Courier New", bold=sel)
            if cat:
                arcade.draw_text(cat, x0 + self.LIST_W - 20, y + 11, (150, 140, 105), 9,
                                 anchor_x="right", font_name="Courier New")
            self._list_rects.append(({"x": x0, "y": y, "w": self.LIST_W - 12, "h": 30}, t))
            y -= 34

    def _fmt(self, val, kind):
        if kind == "bool":
            return "Yes" if val else "No"
        if kind == "float":
            return f"{float(val):.2f}"
        return str(int(val))

    def _draw_editor(self):
        self._buttons = []
        if not self.selected:
            return
        w, h = self.window.width, self.window.height
        ex = 16 + self.LIST_W + 24
        u = self.units[self.selected]
        arcade.draw_text(u.get("name", self.selected), ex, h - 100, (235, 215, 140), 18,
                         font_name="Courier New", bold=True)
        # Preview blob in house colour, sized by 'size'
        col = HOUSES["atreides"]["color"]
        sz = max(8, min(60, int(u.get("size", 16))))
        cx = w - 110
        cy = h - 110
        if u.get("flying"):
            arcade.draw_lrbt_rectangle_filled(cx - sz/2, cx + sz/2, cy - sz/6, cy + sz/6, col)
            arcade.draw_lrbt_rectangle_filled(cx - sz/6, cx + sz/6, cy - sz/2, cy + sz/2, col)
        else:
            arcade.draw_circle_filled(cx, cy, sz / 2, col)
        arcade.draw_text(u.get("category", ""), cx, cy - sz/2 - 16, (160, 150, 110), 10,
                         anchor_x="center", font_name="Courier New")

        y = h - 140
        for label, key, step, kind in FIELDS:
            # Skip flying for clearly-ground infantry/support to reduce clutter? Show all.
            val = u.get(key, 0)
            arcade.draw_text(label, ex, y + 4, (200, 180, 120), 13, font_name="Courier New")
            vx = ex + 230
            if kind == "bool":
                r = draw_button(vx, y, 70, 26, self._fmt(val, kind), active=bool(val))
                self._buttons.append((r, (key, "toggle", kind)))
            else:
                rminus = draw_button(vx, y, 34, 26, "-")
                self._buttons.append((rminus, (key, -step, kind)))
                arcade.draw_text(self._fmt(val, kind), vx + 40 + 45, y + 5, (235, 220, 150), 13,
                                 anchor_x="center", font_name="Courier New")
                rplus = draw_button(vx + 130, y, 34, 26, "+")
                self._buttons.append((rplus, (key, step, kind)))
            y -= 38

        # Action buttons
        y -= 8
        r = draw_button(ex, y, 110, 30, "Save", active=self.dirty)
        self._buttons.append((r, ("__save__", 0, "act")))
        r = draw_button(ex + 120, y, 110, 30, "Reload")
        self._buttons.append((r, ("__reload__", 0, "act")))
        r = draw_button(ex + 240, y, 110, 30, "Menu")
        self._buttons.append((r, ("__menu__", 0, "act")))
        if self.dirty:
            arcade.draw_text("* unsaved changes", ex, y - 24, (230, 170, 90), 11,
                             font_name="Courier New")

    # ----- input -----
    def on_mouse_motion(self, x, y, dx, dy):
        self.mouse_x, self.mouse_y = x, y

    def on_mouse_press(self, x, y, button, mod):
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        for rect, t in self._list_rects:
            if point_in(rect, x, y):
                self.selected = t
                return
        for rect, (key, step, kind) in self._buttons:
            if point_in(rect, x, y):
                self._apply(key, step, kind)
                return

    def on_key_press(self, key, mod):
        if key == arcade.key.ESCAPE:
            self._menu()

    def _apply(self, key, step, kind):
        if key == "__save__":
            self._save(); return
        if key == "__reload__":
            self._reload(); return
        if key == "__menu__":
            self._menu(); return
        u = self.units[self.selected]
        if kind == "bool":
            u[key] = not bool(u.get(key, False))
        elif kind == "int":
            u[key] = max(0, int(u.get(key, 0)) + int(step))
        else:  # float
            u[key] = round(max(0.0, float(u.get(key, 0)) + step), 2)
        self.dirty = True

    def _save(self):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            cfg["units"] = self.units
            with open(CONFIG_PATH, "w") as f:
                json.dump(cfg, f, indent=2)
            # Update in-memory stats in place so references pick up the change.
            for t, vals in self.units.items():
                if t in UNIT_STATS:
                    UNIT_STATS[t].clear()
                    UNIT_STATS[t].update(vals)
                else:
                    UNIT_STATS[t] = dict(vals)
            self.dirty = False
            self._notify("Saved to config.json")
        except Exception as e:
            self._notify(f"Save failed: {e}")

    def _reload(self):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            self.units = copy.deepcopy(cfg.get("units", {}))
            self.order = list(self.units.keys())
            if self.selected not in self.units and self.order:
                self.selected = self.order[0]
            self.dirty = False
            self._notify("Reloaded from disk")
        except Exception as e:
            self._notify(f"Reload failed: {e}")

    def _menu(self):
        from scenes.menu_scene import MenuScene
        self.window.scene_manager.replace(MenuScene(self.window))
