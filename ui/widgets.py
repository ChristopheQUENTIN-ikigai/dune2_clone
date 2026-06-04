"""
Small reusable UI widgets used by the editors and dialogs.

Kept deliberately dependency-light: each widget draws itself with arcade
primitives and is fed events by the owning scene (Arcade dispatches on_text /
on_key_press to the active scene, which forwards them here).
"""
import arcade

FONT = "Courier New"


class TextInput:
    """A single-line editable text field.

    The owning scene forwards typed characters via ``on_text`` and key presses
    (for Backspace) via ``on_key``. Click inside the field's rect to focus it.
    """

    def __init__(self, x, y, w, h=26, value="", placeholder="", max_len=40,
                 allowed=None):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.value = value
        self.placeholder = placeholder
        self.max_len = max_len
        self.active = False
        self.allowed = allowed  # optional set/string of allowed chars

    def set_rect(self, x, y, w=None, h=None):
        self.x, self.y = x, y
        if w is not None:
            self.w = w
        if h is not None:
            self.h = h

    def hit(self, mx, my):
        return self.x <= mx <= self.x + self.w and self.y <= my <= self.y + self.h

    def on_text(self, text):
        if not self.active:
            return
        for ch in text:
            if ch in "\r\n\t":
                continue
            if self.allowed is not None and ch not in self.allowed:
                continue
            if len(self.value) < self.max_len:
                self.value += ch

    def on_key(self, key, modifiers=0):
        if not self.active:
            return
        if key == arcade.key.BACKSPACE:
            self.value = self.value[:-1]

    def draw(self):
        bd = (220, 200, 90) if self.active else (110, 100, 75)
        arcade.draw_lrbt_rectangle_filled(self.x, self.x + self.w, self.y, self.y + self.h,
                                          (24, 20, 14))
        arcade.draw_lrbt_rectangle_outline(self.x, self.x + self.w, self.y, self.y + self.h,
                                           bd, 2 if self.active else 1)
        if self.value:
            txt, col = self.value, (235, 220, 150)
        else:
            txt, col = self.placeholder, (110, 100, 75)
        caret = "_" if self.active else ""
        arcade.draw_text(txt + caret, self.x + 6, self.y + self.h / 2 - 7, col, 12,
                         font_name=FONT)


def draw_button(x, y, w, h, label, enabled=True, active=False, hovered=False,
                size=12):
    """Draw a simple button and return its rect dict (for hit-testing)."""
    if active:
        bg, bd, tc = (80, 70, 40), (220, 200, 80), (255, 230, 120)
    elif not enabled:
        bg, bd, tc = (38, 34, 27), (75, 68, 52), (110, 100, 78)
    elif hovered:
        bg, bd, tc = (74, 64, 44), (180, 158, 92), (240, 220, 140)
    else:
        bg, bd, tc = (56, 48, 34), (150, 132, 80), (215, 196, 128)
    arcade.draw_lrbt_rectangle_filled(x, x + w, y, y + h, bg)
    arcade.draw_lrbt_rectangle_outline(x, x + w, y, y + h, bd, 1)
    arcade.draw_text(label, x + w / 2, y + h / 2 - size * 0.55, tc, size,
                     anchor_x="center", font_name=FONT)
    return {"x": x, "y": y, "w": w, "h": h}


def point_in(rect, mx, my):
    return rect["x"] <= mx <= rect["x"] + rect["w"] and rect["y"] <= my <= rect["y"] + rect["h"]
