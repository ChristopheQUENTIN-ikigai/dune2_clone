"""
Main menu — New Game, Load Game (file browser over saved JSON), Map Editor,
Unit Editor. Save is F5 in-game; Load is F9 in-game or via the browser here.
"""
import arcade
from scenes.scene_manager import Scene
from ui.file_browser import FileBrowser
from settings import SAVES_PATH


class MenuScene(Scene):
    def __init__(self, window):
        super().__init__(window)
        self.selected_index = 0
        self.mouse_x = 0
        self.mouse_y = 0
        self.show_help = False
        self.file_browser = None

    def _get_menu_items(self):
        return [
            ("New Game", True),
            ("Load Game", True),
            ("Map Editor", True),
            ("Unit Editor", True),
            ("Multiplayer (LAN)", False),
            ("Spectator Mode", False),
        ]

    def _get_menu_rect(self, index):
        w, h = self.window.width, self.window.height
        iw, ih, sp = 320, 44, 54
        x = w / 2 - iw / 2
        y = h / 2 + 80 - index * sp
        return x, y, iw, ih

    def _get_hovered_index(self):
        items = self._get_menu_items()
        for i in range(len(items)):
            x, y, bw, bh = self._get_menu_rect(i)
            if x <= self.mouse_x <= x + bw and y <= self.mouse_y <= y + bh:
                return i
        return -1

    def on_show(self):
        arcade.set_background_color((20, 15, 10))

    def on_draw(self):
        self.window.clear()
        w, h = self.window.width, self.window.height
        items = self._get_menu_items()

        arcade.draw_text("DUNE II", w/2, h-80, (220,180,100), 52,
                         anchor_x="center", font_name="Courier New", bold=True)
        arcade.draw_text("The Battle for Arrakis", w/2, h-125, (180,150,80), 18,
                         anchor_x="center", font_name="Courier New")
        arcade.draw_text("House Atreides", w/2-100, h-160, (50,150,255), 13,
                         anchor_x="center", font_name="Courier New")
        arcade.draw_text("vs", w/2, h-160, (180,160,100), 13,
                         anchor_x="center", font_name="Courier New")
        arcade.draw_text("House Harkonnen", w/2+110, h-160, (255,80,80), 13,
                         anchor_x="center", font_name="Courier New")

        hovered = self._get_hovered_index()
        for i, (label, enabled) in enumerate(items):
            x, y, bw, bh = self._get_menu_rect(i)
            sel = (i == self.selected_index)
            hov = (i == hovered)
            if sel or hov:
                bg = (80,65,40,200) if enabled else (50,45,38,200)
                bd = (200,170,80) if enabled else (100,90,70)
            else:
                bg = (40,35,25,180)
                bd = (80,70,50)
            arcade.draw_lrbt_rectangle_filled(x, x+bw, y, y+bh, bg)
            arcade.draw_lrbt_rectangle_outline(x, x+bw, y, y+bh, bd, 2)
            if enabled:
                tc = (240,210,130) if (sel or hov) else (200,180,120)
            else:
                tc = (100,90,70)
            lt = label if enabled else f"{label} (coming soon)"
            arcade.draw_text(lt, x+bw/2, y+bh/2-8, tc, 16,
                             anchor_x="center", font_name="Courier New")
            if sel:
                arcade.draw_text(">", x-20, y+bh/2-10, (220,180,80), 18, font_name="Courier New")

        arcade.draw_text("Press H for help  |  ESC to exit  |  ENTER to select",
                         w/2, 40, (120,110,80), 12, anchor_x="center", font_name="Courier New")
        arcade.draw_text("F5 save / F9 load (in-game)  |  AZERTY: Z/S navigate",
                         w/2, 20, (90,80,60), 10, anchor_x="center", font_name="Courier New")

        if self.show_help:
            self._draw_help_overlay()
        if self.file_browser:
            self.file_browser.draw(self.window)

    def _draw_help_overlay(self):
        w, h = self.window.width, self.window.height
        arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (0,0,0,180))
        bw2, bh2 = 540, 540
        bx, by = w/2-bw2/2, h/2-bh2/2
        arcade.draw_lrbt_rectangle_filled(bx, bx+bw2, by, by+bh2, (30,25,18,240))
        arcade.draw_lrbt_rectangle_outline(bx, bx+bw2, by, by+bh2, (180,150,80), 2)
        arcade.draw_text("HELP - Controls", w/2, by+bh2-35, (220,190,100), 18,
                         anchor_x="center", font_name="Courier New", bold=True)
        lines = [
            "MENU: Z/Up, S/Down navigate | Enter select",
            "Load Game: pick a saved .json from the browser",
            "Map Editor: paint terrain, set starts, save/load maps",
            "Unit Editor: tweak unit stats, save to config",
            "",
            "IN-GAME: Z/Q/S/D scroll | Mouse wheel zoom",
            "Left click: Select | Left drag: Box select",
            "Right click: Move/Attack | Shift+Right: Waypoint",
            "X: Stop | Space: Center base | H: Help",
            "Ctrl+1-5: Set group | 1-5: Recall group",
            "M: Minimap | Enter: Deploy MCV",
            "F5: Quick Save | F9: Quick Load",
            "Escape: Menu / Cancel",
            "",
            "Buildings: CY -> Barracks, Refinery, Solar, Light/Heavy",
            "  Factory, Hi-Tech, Airfield, Gun Turret",
            "Units: soldier, sniper, trike, quad, tank, rocket,",
            "  helicopter, jet fighter, bomber, harvester, MCV",
            "",
            "Press H to close",
        ]
        ly = by + bh2 - 65
        for line in lines:
            arcade.draw_text(line, bx+25, ly, (170,155,115), 11, font_name="Courier New")
            ly -= 22

    # ----- input -----
    def on_key_press(self, key, mod):
        if self.file_browser:
            if self.file_browser.on_key(key):
                self.file_browser = None
            return
        if key == arcade.key.ESCAPE:
            self.window.close(); return
        if key == arcade.key.H:
            self.show_help = not self.show_help; return
        if self.show_help:
            return
        items = self._get_menu_items()
        if key in (arcade.key.Z, arcade.key.UP):
            self.selected_index = (self.selected_index - 1) % len(items)
        elif key in (arcade.key.S, arcade.key.DOWN):
            self.selected_index = (self.selected_index + 1) % len(items)
        elif key in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.SPACE):
            self._activate()

    def on_mouse_motion(self, x, y, dx, dy):
        self.mouse_x, self.mouse_y = x, y
        if self.file_browser:
            return
        h = self._get_hovered_index()
        if h >= 0:
            self.selected_index = h

    def on_mouse_press(self, x, y, button, mod):
        if self.file_browser:
            self.file_browser.on_mouse_press(x, y, button)
            return
        if self.show_help:
            self.show_help = False; return
        if button == arcade.MOUSE_BUTTON_LEFT:
            h = self._get_hovered_index()
            if h >= 0:
                self.selected_index = h; self._activate()

    def on_mouse_scroll(self, x, y, sx, sy):
        if self.file_browser:
            self.file_browser.on_scroll(sy)

    def _activate(self):
        items = self._get_menu_items()
        if self.selected_index >= len(items):
            return
        label, enabled = items[self.selected_index]
        if not enabled:
            return
        if label == "New Game":
            from scenes.game_scene import GameScene
            self.window.scene_manager.replace(GameScene(self.window))
        elif label == "Load Game":
            self._open_load_browser()
        elif label == "Map Editor":
            from scenes.map_editor import MapEditorScene
            self.window.scene_manager.replace(MapEditorScene(self.window))
        elif label == "Unit Editor":
            from scenes.unit_editor import UnitEditorScene
            self.window.scene_manager.replace(UnitEditorScene(self.window))

    def _open_load_browser(self):
        SAVES_PATH.mkdir(parents=True, exist_ok=True)
        self.file_browser = FileBrowser(
            "Load Game", SAVES_PATH, "*.json",
            on_select=self._load_save, on_cancel=self._close_browser)

    def _close_browser(self):
        self.file_browser = None

    def _load_save(self, path):
        self.file_browser = None
        from scenes.game_scene import GameScene
        self.window.scene_manager.replace(
            GameScene(self.window, load_save=True, save_path=str(path)))
