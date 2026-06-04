#!/usr/bin/env python3
"""Headless logic tests for the editor scenes and file browser (no GL window:
only non-drawing methods are exercised)."""
import sys, os, shutil, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import arcade  # noqa: F401 (constants used by scenes)
from settings import MAP_WIDTH, MAP_HEIGHT, MAPS_PATH, CONFIG_PATH, UNIT_STATS
from ui.file_browser import FileBrowser


class FakeWindow:
    def __init__(self, w=1280, h=800):
        self.width = w
        self.height = h
        self._mouse_x = 0
        self._mouse_y = 0
        class _SM:
            def replace(self, scene): self.replaced = scene
        self.scene_manager = _SM()


def test_map_editor_paint_and_startpos():
    from scenes.map_editor import MapEditorScene
    win = FakeWindow()
    ed = MapEditorScene(win)
    ed.cam_x = ed.cam_y = 0.0
    ed.zoom = 1.0
    # Paint tile (10,10): screen x in [320,352), y in [1696,1728) at cam0/zoom1
    ed.brush = "rock"
    ed.brush_size = 1
    ed._paint(330, 1700, erase=False)
    assert ed.gm.tiles[10][10].terrain == "rock", "painted rock"
    # Spice paints spice amount
    ed.brush = "spice"
    ed.spice_amount = 1500
    ed._paint(330, 1700, erase=False)
    assert ed.gm.tiles[10][10].terrain == "spice"
    assert ed.gm.tiles[10][10].spice == 1500
    # Erase back to sand
    ed._paint(330, 1700, erase=True)
    assert ed.gm.tiles[10][10].terrain == "sand"
    assert ed.gm.tiles[10][10].spice == 0
    # Set P1 start at (10,10)
    ed._set_start(330, 1700, 0)
    p1 = [sp for sp in ed.gm.starting_positions if sp["player"] == 0][0]
    assert (p1["x"], p1["y"]) == (10, 10)
    print("[PASS] test_map_editor_paint_and_startpos")


def test_map_editor_save_load():
    from scenes.map_editor import MapEditorScene
    win = FakeWindow()
    ed = MapEditorScene(win)
    ed.cam_x = ed.cam_y = 0.0
    ed.zoom = 1.0
    ed.brush = "mountain"; ed._paint(330, 1700, erase=False)
    ed.name_input.value = "__editor_selftest__"
    ed._save()
    path = MAPS_PATH / "__editor_selftest__.json"
    assert path.exists(), "map file written"
    try:
        ed2 = MapEditorScene(win)
        ed2._load_file(path)
        assert ed2.gm.tiles[10][10].terrain == "mountain", "loaded terrain matches"
    finally:
        if path.exists():
            path.unlink()
    print("[PASS] test_map_editor_save_load")


def test_file_browser_lists_files():
    with tempfile.TemporaryDirectory() as d:
        for n in ("a.json", "b.json", "c.txt"):
            open(os.path.join(d, n), "w").close()
        fb = FileBrowser("T", d, "*.json")
        names = {p.name for p, _, _ in fb.entries}
        assert names == {"a.json", "b.json"}, f"only json listed, got {names}"
    print("[PASS] test_file_browser_lists_files")


def test_unit_editor_edit_and_save():
    from scenes.unit_editor import UnitEditorScene
    backup = open(CONFIG_PATH).read()
    win = FakeWindow()
    try:
        ed = UnitEditorScene(win)
        ed.selected = "tank"
        before = ed.units["tank"]["cost"]
        ed._apply("cost", 25, "int")
        assert ed.units["tank"]["cost"] == before + 25
        assert ed.dirty is True
        ed._apply("flying", 0, "bool")  # toggle
        flying_now = ed.units["tank"]["flying"]
        ed._save()
        assert ed.dirty is False
        # config.json on disk reflects the change
        import json
        disk = json.load(open(CONFIG_PATH))
        assert disk["units"]["tank"]["cost"] == before + 25
        # in-memory stats updated in place
        assert UNIT_STATS["tank"]["cost"] == before + 25
        assert UNIT_STATS["tank"]["flying"] == flying_now
    finally:
        with open(CONFIG_PATH, "w") as f:
            f.write(backup)
        # restore in-memory too
        import json
        for t, v in json.loads(backup)["units"].items():
            if t in UNIT_STATS:
                UNIT_STATS[t].clear(); UNIT_STATS[t].update(v)
    print("[PASS] test_unit_editor_edit_and_save")


if __name__ == "__main__":
    test_map_editor_paint_and_startpos()
    test_map_editor_save_load()
    test_file_browser_lists_files()
    test_unit_editor_edit_and_save()
    print("\n=== ALL SCENE TESTS PASSED ===")
