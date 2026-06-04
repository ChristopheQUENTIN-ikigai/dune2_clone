"""
Scene manager — manages scene stack and transitions.
"""


class Scene:
    """Base scene class."""

    def __init__(self, window):
        self.window = window

    def on_show(self):
        """Called when scene becomes active."""
        pass

    def on_hide(self):
        """Called when scene becomes inactive."""
        pass

    def on_update(self, dt: float):
        pass

    def on_draw(self):
        pass

    def on_key_press(self, key, modifiers):
        pass

    def on_key_release(self, key, modifiers):
        pass

    def on_text(self, text):
        pass

    def on_mouse_press(self, x, y, button, modifiers):
        pass

    def on_mouse_release(self, x, y, button, modifiers):
        pass

    def on_mouse_motion(self, x, y, dx, dy):
        pass

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        pass

    def on_resize(self, width, height):
        pass


class SceneManager:
    """Manages a stack of scenes."""

    def __init__(self, window):
        self.window = window
        self.scenes: list[Scene] = []

    @property
    def current(self) -> Scene | None:
        return self.scenes[-1] if self.scenes else None

    def push(self, scene: Scene):
        if self.current:
            self.current.on_hide()
        self.scenes.append(scene)
        scene.on_show()

    def pop(self):
        if self.scenes:
            old = self.scenes.pop()
            old.on_hide()
            if self.current:
                self.current.on_show()
            return old
        return None

    def replace(self, scene: Scene):
        if self.scenes:
            old = self.scenes.pop()
            old.on_hide()
        self.scenes.append(scene)
        scene.on_show()
