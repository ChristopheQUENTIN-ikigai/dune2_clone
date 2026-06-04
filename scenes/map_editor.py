"""
Map Editor — paint terrain, place spice, set the two starting positions, and
save/load 64x64 maps as JSON (the same format the game loads).

Controls:
  Z/Q/S/D or Arrows  scroll          Mouse wheel  zoom
  Left click         paint with current brush / set start position
  Right click        erase to sand
  G                  toggle grid      Escape  back to menu (or cancel dialog)
The right-hand palette holds terrain swatches, brush size, spice amount, the
start-position tools, and New / Save / Load buttons. Type a filename in the
field before pressing Save.
"""
import arcade
from scenes.scene_manager import Scene
from map.game_map import GameMap
from entities.unit import tile_to_world, world_to_tile
from ui.widgets import TextInput, draw_button, point_in
from ui.file_browser import FileBrowser
from settings import (TILE_SIZE, MAP_WIDTH, MAP_HEIGHT, MAP_PIXEL_WIDTH,
                      MAP_PIXEL_HEIGHT, TERRAIN_COLORS, MAPS_PATH, SCROLL_SPEED,
                      ZOOM_MIN, ZOOM_MAX, ZOOM_STEP, SPICE_PER_TILE_MAX)

PALETTE_W = 250
TERRAINS = ["sand", "rock", "dunes", "spice", "thick_spice", "mountain"]


class MapEditorScene(Scene):
    def __init__(self, window):
        super().__init__(window)
        self.gm = GameMap()
        self.gm.generate_default()
        self.cam_x = self.cam_y = 0.0
        self.zoom = 1.0
        self.keys_held = set()
        self.mouse_x = self.mouse_y = 0
        self.brush = TERRAINS[0]
        self.brush_size = 1
        self.spice_amount = 1000
        self.start_mode = 0          # 0 = paint, 1 = set P1, 2 = set P2
        self.show_grid = True
        self.painting = False
        self.erasing = False
        self.notification = ""
        self.notif_timer = 0.0
        self.file_browser = None
        self.name_input = TextInput(0, 0, PALETTE_W - 24, value="mymap",
                                    placeholder="filename",
                                    allowed="abcdefghijklmnopqrstuvwxyz"
                                            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        self._buttons = []
        self._ensure_start_positions()

    # ----- lifecycle -----
    def on_show(self):
        arcade.set_background_color((18, 16, 12))
        wx, wy = tile_to_world(MAP_WIDTH // 2, MAP_HEIGHT // 2)
        self.cam_x = wx - (self.window.width - PALETTE_W) / 2
        self.cam_y = wy - self.window.height / 2
        self._clamp()

    def _ensure_start_positions(self):
        if len(self.gm.starting_positions) < 2:
            self.gm.starting_positions = [{"player": 0, "x": 5, "y": 5},
                                          {"player": 1, "x": MAP_WIDTH - 9,
                                           "y": MAP_HEIGHT - 9}]

    def _notify(self, m):
        self.notification = m
        self.notif_timer = 2.5

    # ----- coordinate helpers -----
    def _w2s(self, wx, wy):
        return (wx - self.cam_x) * self.zoom, (wy - self.cam_y) * self.zoom

    def _s2w(self, sx, sy):
        return sx / self.zoom + self.cam_x, sy / self.zoom + self.cam_y

    def _clamp(self):
        mx = MAP_PIXEL_WIDTH - (self.window.width - PALETTE_W) / self.zoom
        my = MAP_PIXEL_HEIGHT - self.window.height / self.zoom
        self.cam_x = max(0, min(self.cam_x, max(0, mx)))
        self.cam_y = max(0, min(self.cam_y, max(0, my)))

    # ----- update -----
    def on_update(self, dt):
        if self.notif_timer > 0:
            self.notif_timer -= dt
        if self.file_browser:
            return
        sp = SCROLL_SPEED * dt / self.zoom
        if arcade.key.Z in self.keys_held or arcade.key.UP in self.keys_held: self.cam_y += sp
        if arcade.key.S in self.keys_held or arcade.key.DOWN in self.keys_held: self.cam_y -= sp
        if arcade.key.Q in self.keys_held or arcade.key.LEFT in self.keys_held: self.cam_x -= sp
        if arcade.key.D in self.keys_held or arcade.key.RIGHT in self.keys_held: self.cam_x += sp
        self._clamp()

    # ----- drawing -----
    def on_draw(self):
        self.window.clear()
        self._draw_tiles()
        self._draw_starts()
        self._draw_palette()
        if self.notif_timer > 0:
            arcade.draw_text(self.notification, (self.window.width - PALETTE_W) / 2, 20,
                             (255, 240, 140), 14, anchor_x="center", font_name="Courier New")
        if self.file_browser:
            self.file_browser.draw(self.window)

    def _visible_tile_range(self):
        wl, wb = self._s2w(0, 0)
        wr, wt = self._s2w(self.window.width - PALETTE_W, self.window.height)
        tx0 = max(0, int(wl // TILE_SIZE) - 1)
        tx1 = min(MAP_WIDTH, int(wr // TILE_SIZE) + 2)
        ty_top = max(0, MAP_HEIGHT - 1 - int(wt // TILE_SIZE) - 1)
        ty_bot = min(MAP_HEIGHT, MAP_HEIGHT - int(wb // TILE_SIZE) + 1)
        return tx0, tx1, ty_top, ty_bot

    def _draw_tiles(self):
        tx0, tx1, ty0, ty1 = self._visible_tile_range()
        ts = TILE_SIZE * self.zoom
        for ty in range(ty0, ty1):
            row = self.gm.tiles[ty]
            for tx in range(tx0, tx1):
                tile = row[tx]
                col = TERRAIN_COLORS.get(tile.terrain, (200, 180, 120))
                wx = tx * TILE_SIZE
                wy = (MAP_HEIGHT - 1 - ty) * TILE_SIZE
                sx, sy = self._w2s(wx, wy)
                arcade.draw_lrbt_rectangle_filled(sx, sx + ts, sy, sy + ts, col)
                if self.show_grid and self.zoom >= 0.7:
                    arcade.draw_lrbt_rectangle_outline(sx, sx + ts, sy, sy + ts,
                                                       (0, 0, 0, 40), 1)
        # Highlight hovered brush footprint
        if self.mouse_x < self.window.width - PALETTE_W:
            wx, wy = self._s2w(self.mouse_x, self.mouse_y)
            htx, hty = world_to_tile(wx, wy)
            r = self.brush_size - 1
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    nx, ny = htx + dx, hty + dy
                    if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT:
                        sx, sy = self._w2s(nx * TILE_SIZE, (MAP_HEIGHT - 1 - ny) * TILE_SIZE)
                        arcade.draw_lrbt_rectangle_outline(sx, sx + ts, sy, sy + ts,
                                                           (255, 255, 255, 180), 2)

    def _draw_starts(self):
        colors = {0: (60, 150, 255), 1: (255, 80, 80)}
        ts = TILE_SIZE * self.zoom
        for sp in self.gm.starting_positions:
            pid = sp.get("player", 0)
            sx, sy = self._w2s(sp["x"] * TILE_SIZE, (MAP_HEIGHT - 1 - sp["y"]) * TILE_SIZE)
            c = colors.get(pid, (255, 255, 255))
            arcade.draw_lrbt_rectangle_outline(sx, sx + ts * 3, sy - ts * 2, sy + ts, c, 3)
            arcade.draw_text(f"P{pid+1}", sx + 3, sy + 3, c, 12,
                             font_name="Courier New", bold=True)

    def _draw_palette(self):
        w, h = self.window.width, self.window.height
        px = w - PALETTE_W
        arcade.draw_lrbt_rectangle_filled(px, w, 0, h, (28, 24, 17, 240))
        arcade.draw_line(px, 0, px, h, (80, 70, 50), 2)
        self._buttons = []
        arcade.draw_text("MAP EDITOR", px + PALETTE_W / 2, h - 28, (225, 195, 105), 16,
                         anchor_x="center", font_name="Courier New", bold=True)
        y = h - 56
        arcade.draw_text("Terrain:", px + 12, y, (200, 180, 120), 12, font_name="Courier New")
        y -= 24
        # Terrain swatches (2 columns)
        sw = (PALETTE_W - 30) // 2
        for i, terr in enumerate(TERRAINS):
            col = i % 2
            rowi = i // 2
            bx = px + 12 + col * (sw + 6)
            by = y - rowi * 30
            active = (self.brush == terr and self.start_mode == 0)
            arcade.draw_lrbt_rectangle_filled(bx, bx + sw, by, by + 26,
                                              TERRAIN_COLORS.get(terr, (200, 180, 120)))
            arcade.draw_lrbt_rectangle_outline(bx, bx + sw, by, by + 26,
                                               (255, 230, 110) if active else (70, 62, 46),
                                               3 if active else 1)
            arcade.draw_text(terr[:8], bx + sw / 2, by + 8, (20, 18, 12), 9,
                             anchor_x="center", font_name="Courier New", bold=True)
            self._buttons.append(({"x": bx, "y": by, "w": sw, "h": 26}, ("terrain", terr)))
        y -= 30 * ((len(TERRAINS) + 1) // 2) + 10

        # Brush size
        arcade.draw_text(f"Brush size: {self.brush_size}", px + 12, y, (200, 180, 120), 12,
                         font_name="Courier New")
        y -= 26
        for i, sz in enumerate((1, 2, 3, 5)):
            bx = px + 12 + i * 42
            r = draw_button(bx, y, 38, 24, str(sz), active=(self.brush_size == sz))
            self._buttons.append((r, ("brush", sz)))
        y -= 34

        # Spice amount
        arcade.draw_text(f"Spice/tile: {self.spice_amount}", px + 12, y, (200, 180, 120), 12,
                         font_name="Courier New")
        y -= 26
        r = draw_button(px + 12, y, 38, 24, "-")
        self._buttons.append((r, ("spice", -250)))
        r = draw_button(px + 56, y, 38, 24, "+")
        self._buttons.append((r, ("spice", 250)))
        y -= 36

        # Start positions
        arcade.draw_text("Start positions:", px + 12, y, (200, 180, 120), 12,
                         font_name="Courier New")
        y -= 26
        r = draw_button(px + 12, y, (PALETTE_W - 30) // 2, 26, "Set P1",
                        active=(self.start_mode == 1))
        self._buttons.append((r, ("startmode", 1)))
        r = draw_button(px + 18 + (PALETTE_W - 30) // 2, y, (PALETTE_W - 30) // 2, 26,
                        "Set P2", active=(self.start_mode == 2))
        self._buttons.append((r, ("startmode", 2)))
        y -= 36

        # Grid toggle
        r = draw_button(px + 12, y, PALETTE_W - 24, 24,
                        f"Grid: {'ON' if self.show_grid else 'OFF'}")
        self._buttons.append((r, ("grid", None)))
        y -= 36

        # Filename + Save/Load/New
        arcade.draw_text("File name:", px + 12, y, (200, 180, 120), 11, font_name="Courier New")
        y -= 22
        self.name_input.set_rect(px + 12, y, PALETTE_W - 24, 26)
        self.name_input.draw()
        y -= 36
        r = draw_button(px + 12, y, (PALETTE_W - 30) // 2, 28, "Save")
        self._buttons.append((r, ("save", None)))
        r = draw_button(px + 18 + (PALETTE_W - 30) // 2, y, (PALETTE_W - 30) // 2, 28, "Load")
        self._buttons.append((r, ("load", None)))
        y -= 36
        r = draw_button(px + 12, y, (PALETTE_W - 30) // 2, 28, "New")
        self._buttons.append((r, ("new", None)))
        r = draw_button(px + 18 + (PALETTE_W - 30) // 2, y, (PALETTE_W - 30) // 2, 28, "Menu")
        self._buttons.append((r, ("menu", None)))

    # ----- input -----
    def on_key_press(self, key, mod):
        self.keys_held.add(key)
        if self.file_browser:
            if self.file_browser.on_key(key):
                self.file_browser = None
            return
        if self.name_input.active:
            if key in (arcade.key.ENTER, arcade.key.RETURN):
                self.name_input.active = False
                self._save()
            elif key == arcade.key.ESCAPE:
                self.name_input.active = False
            else:
                self.name_input.on_key(key, mod)
            return
        if key == arcade.key.ESCAPE:
            self._back()
        elif key == arcade.key.G:
            self.show_grid = not self.show_grid

    def on_key_release(self, key, mod):
        self.keys_held.discard(key)

    def on_text(self, text):
        if self.name_input.active and not self.file_browser:
            self.name_input.on_text(text)

    def on_mouse_motion(self, x, y, dx, dy):
        self.mouse_x, self.mouse_y = x, y

    def on_mouse_press(self, x, y, button, mod):
        self.mouse_x, self.mouse_y = x, y
        if self.file_browser:
            if self.file_browser.on_mouse_press(x, y, button):
                pass
            return
        if x >= self.window.width - PALETTE_W:
            self._palette_click(x, y)
            return
        # Click on the map
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.name_input.active = False
            if self.start_mode in (1, 2):
                self._set_start(x, y, self.start_mode - 1)
            else:
                self.painting = True
                self._paint(x, y, erase=False)
        elif button == arcade.MOUSE_BUTTON_RIGHT:
            self.erasing = True
            self._paint(x, y, erase=True)

    def on_mouse_release(self, x, y, button, mod):
        self.painting = False
        self.erasing = False

    def on_mouse_drag(self, x, y, dx, dy, buttons, mod):
        self.mouse_x, self.mouse_y = x, y
        if self.file_browser or x >= self.window.width - PALETTE_W:
            return
        if self.painting:
            self._paint(x, y, erase=False)
        elif self.erasing:
            self._paint(x, y, erase=True)

    def on_mouse_scroll(self, x, y, sx, sy):
        if self.file_browser:
            self.file_browser.on_scroll(sy)
            return
        oz = self.zoom
        if sy > 0:
            self.zoom = min(ZOOM_MAX, self.zoom + ZOOM_STEP)
        elif sy < 0:
            self.zoom = max(ZOOM_MIN, self.zoom - ZOOM_STEP)
        if oz != self.zoom:
            wx, wy = x / oz + self.cam_x, y / oz + self.cam_y
            self.cam_x = wx - x / self.zoom
            self.cam_y = wy - y / self.zoom
            self._clamp()

    # ----- actions -----
    def _palette_click(self, x, y):
        if self.name_input.hit(x, y):
            self.name_input.active = True
            return
        self.name_input.active = False
        for rect, (kind, val) in self._buttons:
            if point_in(rect, x, y):
                if kind == "terrain":
                    self.brush = val
                    self.start_mode = 0
                elif kind == "brush":
                    self.brush_size = val
                elif kind == "spice":
                    self.spice_amount = max(0, min(int(SPICE_PER_TILE_MAX * 2),
                                                   self.spice_amount + val))
                elif kind == "startmode":
                    self.start_mode = 0 if self.start_mode == val else val
                elif kind == "grid":
                    self.show_grid = not self.show_grid
                elif kind == "save":
                    self._save()
                elif kind == "load":
                    self._open_load()
                elif kind == "new":
                    self._new_map()
                elif kind == "menu":
                    self._back()
                return

    def _paint(self, sx, sy, erase):
        wx, wy = self._s2w(sx, sy)
        tx, ty = world_to_tile(wx, wy)
        terr = "sand" if erase else self.brush
        r = self.brush_size - 1
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = tx + dx, ty + dy
                tile = self.gm.get_tile(nx, ny)
                if not tile:
                    continue
                tile.terrain = terr
                if terr == "spice":
                    tile.spice = self.spice_amount
                elif terr == "thick_spice":
                    tile.spice = self.spice_amount * 2
                else:
                    tile.spice = 0

    def _set_start(self, sx, sy, pid):
        wx, wy = self._s2w(sx, sy)
        tx, ty = world_to_tile(wx, wy)
        tx = max(0, min(MAP_WIDTH - 3, tx))
        ty = max(0, min(MAP_HEIGHT - 3, ty))
        for sp in self.gm.starting_positions:
            if sp.get("player") == pid:
                sp["x"], sp["y"] = tx, ty
                break
        else:
            self.gm.starting_positions.append({"player": pid, "x": tx, "y": ty})
        self._notify(f"P{pid+1} start set to ({tx},{ty})")
        self.start_mode = 0

    def _save(self):
        name = (self.name_input.value or "mymap").strip()
        if not name.endswith(".json"):
            name += ".json"
        MAPS_PATH.mkdir(parents=True, exist_ok=True)
        path = MAPS_PATH / name
        self._ensure_start_positions()
        self.gm.save_to_json(str(path))
        self._notify(f"Saved {name}")

    def _open_load(self):
        self.file_browser = FileBrowser(
            "Load Map", MAPS_PATH, "*.json",
            on_select=self._load_file, on_cancel=self._close_browser)

    def _close_browser(self):
        self.file_browser = None

    def _load_file(self, path):
        try:
            self.gm = GameMap()
            self.gm.load_from_json(str(path))
            self._ensure_start_positions()
            self._notify(f"Loaded {path.name}")
            self.name_input.value = path.stem
        except Exception as e:
            self._notify(f"Load failed: {e}")
        self.file_browser = None

    def _new_map(self):
        self.gm = GameMap()
        self.gm._init_empty()
        self.gm.starting_positions = [{"player": 0, "x": 5, "y": 5},
                                      {"player": 1, "x": MAP_WIDTH - 9, "y": MAP_HEIGHT - 9}]
        self._notify("New blank map")

    def _back(self):
        from scenes.menu_scene import MenuScene
        self.window.scene_manager.replace(MenuScene(self.window))

    def on_resize(self, w, h):
        self._clamp()
