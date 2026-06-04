#!/usr/bin/env python3
"""
Dune 2 Clone - Main entry point.
Run: python main.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from settings import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
    WINDOW_RESIZABLE, ensure_directories
)


def generate_assets_if_needed():
    from settings import TEXTURES_PATH
    if not (TEXTURES_PATH / "terrain" / "sand.png").exists():
        print("Generating textures...")
        from gen_textures import main as gen_main
        gen_main()


def generate_default_map_if_needed():
    from settings import DEFAULT_MAP_PATH
    if not DEFAULT_MAP_PATH.exists():
        print("Generating default map...")
        from map.game_map import GameMap
        gm = GameMap()
        gm.generate_default()
        gm.save_to_json(str(DEFAULT_MAP_PATH))
        print(f"Map saved to {DEFAULT_MAP_PATH}")


def main():
    ensure_directories()
    generate_assets_if_needed()
    generate_default_map_if_needed()

    import arcade

    class DuneWindow(arcade.Window):
        def __init__(self):
            super().__init__(
                width=WINDOW_WIDTH,
                height=WINDOW_HEIGHT,
                title=WINDOW_TITLE,
                resizable=WINDOW_RESIZABLE,
            )
            from scenes.scene_manager import SceneManager
            self.scene_manager = SceneManager(self)
            self._mouse_x = 0
            self._mouse_y = 0

        def setup(self):
            from scenes.menu_scene import MenuScene
            self.scene_manager.push(MenuScene(self))

        def on_update(self, dt):
            if self.scene_manager.current:
                self.scene_manager.current.on_update(dt)

        def on_draw(self):
            if self.scene_manager.current:
                self.scene_manager.current.on_draw()

        def on_key_press(self, key, modifiers):
            if self.scene_manager.current:
                self.scene_manager.current.on_key_press(key, modifiers)

        def on_key_release(self, key, modifiers):
            if self.scene_manager.current:
                self.scene_manager.current.on_key_release(key, modifiers)

        def on_text(self, text):
            if self.scene_manager.current:
                self.scene_manager.current.on_text(text)

        def on_mouse_press(self, x, y, button, modifiers):
            self._mouse_x, self._mouse_y = x, y
            if self.scene_manager.current:
                self.scene_manager.current.on_mouse_press(x, y, button, modifiers)

        def on_mouse_release(self, x, y, button, modifiers):
            if self.scene_manager.current:
                self.scene_manager.current.on_mouse_release(x, y, button, modifiers)

        def on_mouse_motion(self, x, y, dx, dy):
            self._mouse_x, self._mouse_y = x, y
            if self.scene_manager.current:
                self.scene_manager.current.on_mouse_motion(x, y, dx, dy)

        def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
            self._mouse_x, self._mouse_y = x, y
            if self.scene_manager.current:
                self.scene_manager.current.on_mouse_drag(x, y, dx, dy, buttons, modifiers)

        def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
            if self.scene_manager.current:
                self.scene_manager.current.on_mouse_scroll(x, y, scroll_x, scroll_y)

        def on_resize(self, width, height):
            super().on_resize(width, height)
            if self.scene_manager.current:
                self.scene_manager.current.on_resize(width, height)

    window = DuneWindow()
    window.setup()
    arcade.run()


if __name__ == "__main__":
    main()
