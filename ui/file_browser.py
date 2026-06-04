"""
FileBrowser — a modal overlay that lists files in a directory and lets the user
pick one. Used both by the main menu (load a saved game from saves/*.json) and
by the Map Editor (load a map from assets/maps/*.json).

It is not a Scene: the owning scene holds one and forwards draw / mouse / scroll
events to it while it is open, then acts on the selected path via a callback.
"""
import os
from pathlib import Path
import arcade

FONT = "Courier New"


class FileBrowser:
    def __init__(self, title, directory, pattern="*.json",
                 on_select=None, on_cancel=None):
        self.title = title
        self.directory = Path(directory)
        self.pattern = pattern
        self.on_select = on_select
        self.on_cancel = on_cancel
        self.scroll = 0
        self.row_rects = []   # (rect, path) populated each draw
        self.cancel_rect = None
        self.refresh()

    def refresh(self):
        self.entries = []
        try:
            files = sorted(self.directory.glob(self.pattern),
                           key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            files = []
        for p in files:
            try:
                st = p.stat()
                size_kb = max(1, st.st_size // 1024)
                import time
                mod = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
            except OSError:
                size_kb, mod = 0, "?"
            self.entries.append((p, f"{size_kb} KB", mod))
        self.scroll = 0

    # --- layout ---
    def _panel(self, window):
        w, h = window.width, window.height
        pw, ph = min(680, w - 80), min(520, h - 100)
        px, py = (w - pw) / 2, (h - ph) / 2
        return px, py, pw, ph

    def draw(self, window):
        w, h = window.width, window.height
        arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (0, 0, 0, 190))
        px, py, pw, ph = self._panel(window)
        arcade.draw_lrbt_rectangle_filled(px, px + pw, py, py + ph, (30, 25, 18, 250))
        arcade.draw_lrbt_rectangle_outline(px, px + pw, py, py + ph, (185, 155, 85), 2)
        arcade.draw_text(self.title, px + pw / 2, py + ph - 34, (225, 195, 105), 18,
                         anchor_x="center", font_name=FONT, bold=True)
        arcade.draw_text(str(self.directory), px + pw / 2, py + ph - 56,
                         (150, 138, 100), 10, anchor_x="center", font_name=FONT)

        # List region
        list_top = py + ph - 74
        list_bottom = py + 52
        row_h = 30
        visible = max(1, int((list_top - list_bottom) // row_h))
        self.row_rects = []

        if not self.entries:
            arcade.draw_text("(no files found)", px + pw / 2, (list_top + list_bottom) / 2,
                             (160, 150, 110), 13, anchor_x="center", font_name=FONT)
        else:
            self.scroll = max(0, min(self.scroll, max(0, len(self.entries) - visible)))
            mx, my = getattr(window, "_mouse_x", -1), getattr(window, "_mouse_y", -1)
            for i in range(self.scroll, min(len(self.entries), self.scroll + visible)):
                p, size_s, mod_s = self.entries[i]
                ry = list_top - (i - self.scroll + 1) * row_h
                rect = {"x": px + 14, "y": ry, "w": pw - 28, "h": row_h - 4}
                hov = rect["x"] <= mx <= rect["x"] + rect["w"] and rect["y"] <= my <= rect["y"] + rect["h"]
                bg = (70, 60, 42) if hov else (46, 40, 28)
                arcade.draw_lrbt_rectangle_filled(rect["x"], rect["x"] + rect["w"],
                                                  rect["y"], rect["y"] + rect["h"], bg)
                arcade.draw_lrbt_rectangle_outline(rect["x"], rect["x"] + rect["w"],
                                                   rect["y"], rect["y"] + rect["h"],
                                                   (150, 132, 80) if hov else (90, 80, 58), 1)
                arcade.draw_text(p.name, rect["x"] + 10, rect["y"] + rect["h"] / 2 - 7,
                                 (235, 220, 150) if hov else (205, 188, 128), 12, font_name=FONT)
                arcade.draw_text(f"{mod_s}   {size_s}", rect["x"] + rect["w"] - 10,
                                 rect["y"] + rect["h"] / 2 - 6, (150, 140, 105), 9,
                                 anchor_x="right", font_name=FONT)
                self.row_rects.append((rect, p))

            if len(self.entries) > visible:
                arcade.draw_text("scroll for more", px + pw / 2, list_bottom - 2,
                                 (140, 128, 95), 9, anchor_x="center", font_name=FONT)

        # Cancel button
        cw, ch = 120, 30
        cx, cy = px + pw / 2 - cw / 2, py + 12
        mx, my = getattr(window, "_mouse_x", -1), getattr(window, "_mouse_y", -1)
        hov = cx <= mx <= cx + cw and cy <= my <= cy + ch
        arcade.draw_lrbt_rectangle_filled(cx, cx + cw, cy, cy + ch,
                                          (74, 64, 44) if hov else (52, 45, 32))
        arcade.draw_lrbt_rectangle_outline(cx, cx + cw, cy, cy + ch, (160, 140, 85), 1)
        arcade.draw_text("Cancel (Esc)", cx + cw / 2, cy + ch / 2 - 7,
                         (225, 205, 135), 12, anchor_x="center", font_name=FONT)
        self.cancel_rect = {"x": cx, "y": cy, "w": cw, "h": ch}

    # --- events: return True if the browser consumed/closed ---
    def on_mouse_press(self, x, y, button):
        if self.cancel_rect and _hit(self.cancel_rect, x, y):
            if self.on_cancel:
                self.on_cancel()
            return True
        for rect, path in self.row_rects:
            if _hit(rect, x, y):
                if self.on_select:
                    self.on_select(path)
                return True
        return False

    def on_scroll(self, dy):
        self.scroll -= int(dy)
        if self.scroll < 0:
            self.scroll = 0

    def on_key(self, key):
        if key == arcade.key.ESCAPE:
            if self.on_cancel:
                self.on_cancel()
            return True
        return False


def _hit(rect, x, y):
    return rect["x"] <= x <= rect["x"] + rect["w"] and rect["y"] <= y <= rect["y"] + rect["h"]
