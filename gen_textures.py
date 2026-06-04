#!/usr/bin/env python3
"""
Procedural texture generator for Dune 2 Clone.
Generates all placeholder PNG textures for terrain, buildings, and units.
Run this once to populate ./assets/textures/
"""
import os
import sys
import random
import struct
import zlib
from pathlib import Path

# Minimal PNG writer (no PIL dependency)

def make_png(width: int, height: int, pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    """Create a PNG file from RGBA pixel data. pixels[y][x] = (r, g, b, a)"""
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))

    raw = b''
    for row in pixels:
        raw += b'\x00'  # filter none
        for r, g, b, a in row:
            raw += struct.pack("BBBB", r, g, b, a)

    idat = chunk(b'IDAT', zlib.compress(raw, 9))
    iend = chunk(b'IEND', b'')
    return header + ihdr + idat + iend


def save_png(path: str, width: int, height: int, pixels):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(make_png(width, height, pixels))
    print(f"  Generated: {path}")


def filled_rect(w, h, color, alpha=255):
    """Solid filled rectangle."""
    return [[(color[0], color[1], color[2], alpha) for _ in range(w)] for _ in range(h)]


def noisy_rect(w, h, base_color, noise=15, alpha=255):
    """Rectangle with per-pixel color noise for natural look."""
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            r = max(0, min(255, base_color[0] + random.randint(-noise, noise)))
            g = max(0, min(255, base_color[1] + random.randint(-noise, noise)))
            b = max(0, min(255, base_color[2] + random.randint(-noise, noise)))
            row.append((r, g, b, alpha))
        pixels.append(row)
    return pixels


def add_border(pixels, w, h, color, thickness=1):
    """Add a border to existing pixel data."""
    for y in range(h):
        for x in range(w):
            if x < thickness or x >= w - thickness or y < thickness or y >= h - thickness:
                pixels[y][x] = (color[0], color[1], color[2], 255)
    return pixels


def add_circle(pixels, cx, cy, radius, color):
    """Draw a filled circle onto pixel data."""
    h = len(pixels)
    w = len(pixels[0]) if h > 0 else 0
    for y in range(max(0, cy - radius), min(h, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(w, cx + radius + 1)):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                pixels[y][x] = (color[0], color[1], color[2], 255)
    return pixels


def add_rect_on(pixels, rx, ry, rw, rh, color):
    """Draw a filled rectangle onto pixel data."""
    h = len(pixels)
    w = len(pixels[0]) if h > 0 else 0
    for y in range(max(0, ry), min(h, ry + rh)):
        for x in range(max(0, rx), min(w, rx + rw)):
            pixels[y][x] = (color[0], color[1], color[2], 255)
    return pixels


def add_cross(pixels, cx, cy, size, color):
    """Draw a + cross."""
    h = len(pixels)
    w = len(pixels[0]) if h > 0 else 0
    for i in range(-size, size + 1):
        if 0 <= cy + i < h and 0 <= cx < w:
            pixels[cy + i][cx] = (color[0], color[1], color[2], 255)
        if 0 <= cy < h and 0 <= cx + i < w:
            pixels[cy][cx + i] = (color[0], color[1], color[2], 255)
    return pixels


def add_dune_waves(pixels, w, h, highlight, shadow, wave_count=3):
    """Add wavy dune lines for visual texture."""
    import math
    for i in range(wave_count):
        y_base = h // (wave_count + 1) * (i + 1)
        for x in range(w):
            y = int(y_base + 2 * math.sin(x * 0.3 + i * 1.5))
            if 0 <= y < h:
                pixels[y][x] = (highlight[0], highlight[1], highlight[2], 255)
            if 0 <= y + 1 < h:
                pixels[y + 1][x] = (shadow[0], shadow[1], shadow[2], 255)
    return pixels


def add_spice_dots(pixels, w, h, dot_color, count=30, dot_size=1):
    """Add scattered dots representing spice."""
    for _ in range(count):
        x = random.randint(2, w - 3)
        y = random.randint(2, h - 3)
        for dy in range(-dot_size, dot_size + 1):
            for dx in range(-dot_size, dot_size + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    pixels[ny][nx] = (dot_color[0], dot_color[1], dot_color[2], 255)
    return pixels


# ---------------------------------------------------------------------------
# TERRAIN TEXTURES (32x32)
# ---------------------------------------------------------------------------
def gen_terrain(base_dir: str):
    ts = 32
    d = os.path.join(base_dir, "terrain")

    # Sand
    px = noisy_rect(ts, ts, (210, 180, 120), noise=12)
    save_png(os.path.join(d, "sand.png"), ts, ts, px)

    # Rock
    px = noisy_rect(ts, ts, (130, 110, 90), noise=10)
    # Add some cracks
    for _ in range(4):
        x = random.randint(4, ts - 5)
        y = random.randint(4, ts - 5)
        for i in range(random.randint(3, 8)):
            nx = min(ts - 1, x + i)
            if 0 <= y < ts and 0 <= nx < ts:
                pixels_val = px[y][nx]
                px[y][nx] = (pixels_val[0] - 20, pixels_val[1] - 20, pixels_val[2] - 20, 255)
    save_png(os.path.join(d, "rock.png"), ts, ts, px)

    # Dunes
    px = noisy_rect(ts, ts, (230, 200, 130), noise=10)
    add_dune_waves(px, ts, ts, (245, 220, 150), (200, 170, 110))
    save_png(os.path.join(d, "dunes.png"), ts, ts, px)

    # Spice
    px = noisy_rect(ts, ts, (200, 140, 60), noise=15)
    add_spice_dots(px, ts, ts, (240, 170, 50), count=20, dot_size=1)
    save_png(os.path.join(d, "spice.png"), ts, ts, px)

    # Thick Spice
    px = noisy_rect(ts, ts, (180, 100, 30), noise=15)
    add_spice_dots(px, ts, ts, (220, 130, 20), count=40, dot_size=1)
    add_spice_dots(px, ts, ts, (255, 180, 40), count=15, dot_size=0)
    save_png(os.path.join(d, "thick_spice.png"), ts, ts, px)

    # Mountain
    px = noisy_rect(ts, ts, (80, 70, 60), noise=8)
    # Mountain peaks
    mid = ts // 2
    for peak_x in [mid - 6, mid, mid + 6]:
        for dy in range(0, 12):
            width = max(1, 8 - dy)
            for dx in range(-width, width + 1):
                x = peak_x + dx
                y = mid + 4 - dy
                if 0 <= x < ts and 0 <= y < ts:
                    shade = min(255, 100 + dy * 8)
                    px[y][x] = (shade - 20, shade - 25, shade - 30, 255)
    # Snow caps
    for peak_x in [mid - 6, mid, mid + 6]:
        for dx in range(-2, 3):
            x = peak_x + dx
            y = mid + 4 - 11
            if 0 <= x < ts and 0 <= y < ts:
                px[y][x] = (220, 220, 230, 255)
    save_png(os.path.join(d, "mountain.png"), ts, ts, px)


# ---------------------------------------------------------------------------
# BUILDING TEXTURES
# ---------------------------------------------------------------------------
def gen_building(base_dir: str, name: str, size_tiles: tuple, house_color: tuple,
                 detail_func=None):
    ts = 32
    w = size_tiles[0] * ts
    h = size_tiles[1] * ts
    d = os.path.join(base_dir, "buildings")

    # Base: darker version of house color
    base = (house_color[0] // 2 + 40, house_color[1] // 2 + 40, house_color[2] // 2 + 40)
    px = noisy_rect(w, h, base, noise=8)

    # Border in house color
    add_border(px, w, h, house_color, thickness=2)

    # Details
    if detail_func:
        detail_func(px, w, h, house_color)

    save_png(os.path.join(d, name), w, h, px)


def detail_construction_yard(px, w, h, color):
    """Construction yard: central gear/cross motif."""
    cx, cy = w // 2, h // 2
    add_circle(px, cx, cy, min(w, h) // 4, color)
    add_cross(px, cx, cy, min(w, h) // 5,
              (min(255, color[0] + 60), min(255, color[1] + 60), min(255, color[2] + 60)))
    # Corner blocks
    s = 8
    for ox, oy in [(4, 4), (w - s - 4, 4), (4, h - s - 4), (w - s - 4, h - s - 4)]:
        add_rect_on(px, ox, oy, s, s, color)


def detail_refinery(px, w, h, color):
    """Refinery: silos and pipe."""
    # Two silos
    add_circle(px, w // 3, h // 2, 10, (180, 140, 60))
    add_circle(px, 2 * w // 3, h // 2, 10, (180, 140, 60))
    # Pipe connecting
    add_rect_on(px, w // 3, h // 2 - 2, w // 3, 4, (150, 120, 50))
    # Spice color accent
    add_rect_on(px, 4, h - 12, w - 8, 8, (200, 150, 50))


def detail_solar_plant(px, w, h, color):
    """Solar plant: solar panels grid."""
    panel_color = (50, 50, 180)
    glare = (100, 100, 220)
    pw, ph = (w - 16) // 2, (h - 16) // 2
    for i in range(2):
        for j in range(2):
            px2 = 6 + i * (pw + 4)
            py2 = 6 + j * (ph + 4)
            add_rect_on(px, px2, py2, pw, ph, panel_color)
            add_rect_on(px, px2 + 2, py2 + 2, pw // 2, 2, glare)


def detail_barracks(px, w, h, color):
    """Barracks: door and windows."""
    # Door
    dw, dh = w // 3, h // 2
    dx = w // 2 - dw // 2
    dy = h - dh - 4
    add_rect_on(px, dx, dy, dw, dh, (60, 50, 40))
    # Door frame
    add_rect_on(px, dx, dy, dw, 2, color)
    add_rect_on(px, dx, dy, 2, dh, color)
    add_rect_on(px, dx + dw - 2, dy, 2, dh, color)
    # Windows
    ww, wh = 6, 6
    add_rect_on(px, 6, 6, ww, wh, (140, 180, 200))
    add_rect_on(px, w - 6 - ww, 6, ww, wh, (140, 180, 200))
    # Flag/marker on top
    add_rect_on(px, w // 2 - 1, 2, 2, 10, (200, 200, 200))
    add_rect_on(px, w // 2 + 1, 2, 6, 4, color)


def detail_heavy_factory(px, w, h, color):
    """Heavy factory: large rolling door, hazard stripes and a gantry crane."""
    # Rolling door
    dw, dh = int(w * 0.5), int(h * 0.45)
    dx, dy = w // 2 - dw // 2, h - dh - 6
    add_rect_on(px, dx, dy, dw, dh, (45, 45, 50))
    for i in range(1, 5):  # door slats
        sy = dy + i * dh // 5
        add_rect_on(px, dx, sy, dw, 1, (70, 70, 78))
    # Hazard stripes along the bottom
    for sx in range(4, w - 4, 8):
        add_rect_on(px, sx, h - 8, 4, 4, (210, 180, 40))
        add_rect_on(px, sx + 4, h - 8, 4, 4, (40, 40, 40))
    # Gantry crane rail across the top
    add_rect_on(px, 6, 8, w - 12, 3, (150, 150, 160))
    add_rect_on(px, w // 2 - 2, 8, 4, h // 3, (120, 120, 130))
    # Corner rivets
    for ox, oy in [(4, 4), (w - 9, 4), (4, h - 9), (w - 9, h - 9)]:
        add_rect_on(px, ox, oy, 5, 5, color)


def detail_gun_turret(px, w, h, color):
    """Gun turret: armoured base, central dome and a barrel angled up-right."""
    cx, cy = w // 2, h // 2 + 2
    # Armoured base plate
    add_rect_on(px, 4, h // 2, w - 8, h // 2 - 4, (70, 70, 75))
    # Rotating dome
    add_circle(px, cx, cy, min(w, h) // 4, (90, 90, 98))
    add_circle(px, cx, cy, min(w, h) // 6, (120, 120, 128))
    # Barrel (points up-right)
    for i in range(0, int(min(w, h) * 0.5)):
        bx, by = cx + i, cy - i
        for t in (-1, 0, 1):
            if 0 <= bx + t < w and 0 <= by < h:
                px[by][bx + t] = (40, 40, 44, 255)
    # Muzzle accent in house color
    add_rect_on(px, cx - 2, cy - 2, 4, 4, color)


def detail_light_factory(px, w, h, color):
    """Light factory: open bay with a small vehicle ramp and antenna."""
    # Vehicle bay door
    dw, dh = int(w * 0.55), int(h * 0.4)
    dx, dy = w // 2 - dw // 2, h - dh - 6
    add_rect_on(px, dx, dy, dw, dh, (48, 48, 54))
    for i in range(1, 4):
        add_rect_on(px, dx, dy + i * dh // 4, dw, 1, (78, 78, 86))
    # Ramp stripes
    for sx in range(dx, dx + dw, 8):
        add_rect_on(px, sx, h - 7, 4, 4, (210, 180, 40))
        add_rect_on(px, sx + 4, h - 7, 4, 4, (40, 40, 40))
    # Antenna / light mast
    add_rect_on(px, 8, 6, 2, h // 3, (160, 160, 170))
    add_circle(px, 9, 6, 2, (230, 120, 80))
    # Corner rivets
    for ox, oy in [(4, 4), (w - 9, 4), (4, h - 9), (w - 9, h - 9)]:
        add_rect_on(px, ox, oy, 5, 5, color)


def detail_hi_tech(px, w, h, color):
    """Hi-Tech factory: domed roof with a helipad H marking."""
    cx, cy = w // 2, h // 2
    # Dome
    add_circle(px, cx, cy, min(w, h) // 3, (70, 80, 110))
    add_circle(px, cx, cy, min(w, h) // 4, (95, 110, 150))
    # Helipad "H"
    hh = min(w, h) // 5
    add_rect_on(px, cx - hh, cy - hh, 3, hh * 2, (230, 230, 235))
    add_rect_on(px, cx + hh - 3, cy - hh, 3, hh * 2, (230, 230, 235))
    add_rect_on(px, cx - hh, cy - 1, hh * 2, 3, (230, 230, 235))
    # Corner sensors
    for ox, oy in [(4, 4), (w - 9, 4), (4, h - 9), (w - 9, h - 9)]:
        add_rect_on(px, ox, oy, 5, 5, color)


def detail_airfield(px, w, h, color):
    """Airfield: runway strip with centre dashes and a control tower."""
    # Runway
    add_rect_on(px, 6, h // 2 - 5, w - 12, 10, (55, 55, 60))
    for sx in range(10, w - 10, 10):
        add_rect_on(px, sx, h // 2 - 1, 6, 2, (220, 220, 120))
    # Control tower (left)
    add_rect_on(px, 8, 6, 10, h // 2 - 6, (90, 90, 98))
    add_rect_on(px, 7, 4, 12, 4, (130, 150, 170))
    # Windsock / beacon (right)
    add_circle(px, w - 12, 10, 3, (230, 120, 80))
    # Corner rivets
    for ox, oy in [(4, 4), (w - 9, 4), (4, h - 9), (w - 9, h - 9)]:
        add_rect_on(px, ox, oy, 5, 5, color)


def gen_buildings(base_dir: str):
    for house_key, house_data in [("atreides", (0, 100, 200)), ("harkonnen", (200, 30, 30))]:
        gen_building(base_dir, f"construction_yard_{house_key}.png", (3, 3),
                     house_data, detail_construction_yard)
        gen_building(base_dir, f"refinery_{house_key}.png", (3, 2),
                     house_data, detail_refinery)
        gen_building(base_dir, f"solar_plant_{house_key}.png", (2, 2),
                     house_data, detail_solar_plant)
        gen_building(base_dir, f"barracks_{house_key}.png", (2, 2),
                     house_data, detail_barracks)
        gen_building(base_dir, f"heavy_factory_{house_key}.png", (3, 3),
                     house_data, detail_heavy_factory)
        gen_building(base_dir, f"gun_turret_{house_key}.png", (2, 2),
                     house_data, detail_gun_turret)
        gen_building(base_dir, f"light_factory_{house_key}.png", (3, 2),
                     house_data, detail_light_factory)
        gen_building(base_dir, f"hi_tech_{house_key}.png", (2, 2),
                     house_data, detail_hi_tech)
        gen_building(base_dir, f"airfield_{house_key}.png", (3, 2),
                     house_data, detail_airfield)


# ---------------------------------------------------------------------------
# UNIT TEXTURES
# ---------------------------------------------------------------------------
def gen_unit(base_dir: str, name: str, size: int, house_color: tuple, detail_func=None):
    d = os.path.join(base_dir, "units")
    px = [[(0, 0, 0, 0) for _ in range(size)] for _ in range(size)]  # transparent

    # Base circle
    cx, cy = size // 2, size // 2
    r = size // 2 - 1
    add_circle(px, cx, cy, r, house_color)

    if detail_func:
        detail_func(px, size, house_color)

    save_png(os.path.join(d, name), size, size, px)


def detail_soldier(px, size, color):
    """Small person silhouette on circle."""
    cx = size // 2
    # Head
    add_circle(px, cx, size // 4, 2, (220, 200, 170))
    # Body line
    for y in range(size // 4 + 2, size // 2 + 3):
        if 0 <= y < size:
            px[y][cx] = (220, 200, 170, 255)
    # Arms
    if size > 10:
        for dx in [-2, -1, 1, 2]:
            ax = cx + dx
            ay = size // 3 + 2
            if 0 <= ax < size and 0 <= ay < size:
                px[ay][ax] = (220, 200, 170, 255)


def detail_harvester(px, size, color):
    """Harvester: blocky with scoop."""
    # Make it more rectangular
    s4 = size // 4
    add_rect_on(px, s4, s4, size // 2, size // 2, (180, 160, 80))
    # Scoop at front
    add_rect_on(px, s4 - 2, size // 2, size // 2 + 4, s4, (160, 140, 60))
    # Spice in scoop
    add_rect_on(px, s4, size // 2 + 2, size // 2, s4 - 4, (220, 160, 40))


def detail_mcv(px, size, color):
    """MCV: large vehicle with construction crane."""
    s4 = size // 4
    # Body
    add_rect_on(px, s4 - 2, s4, size // 2 + 4, size // 2, color)
    # Crane arm
    for y in range(2, s4 + 2):
        x = size // 2 + s4 - 2
        if 0 <= x < size and 0 <= y < size:
            px[y][x] = (200, 200, 200, 255)
            if x + 1 < size:
                px[y][x + 1] = (200, 200, 200, 255)
    # Tracks
    add_rect_on(px, s4 - 3, s4 + size // 2 - 2, size // 2 + 6, 3, (60, 60, 60))


def _lighten(color, amt=50):
    return (min(255, color[0] + amt), min(255, color[1] + amt), min(255, color[2] + amt))


def _darken(color, amt=50):
    return (max(0, color[0] - amt), max(0, color[1] - amt), max(0, color[2] - amt))


def detail_trike(px, size, color):
    """Trike: small three-wheeled buggy with a light gun."""
    cx, cy = size // 2, size // 2
    add_rect_on(px, cx - 3, cy - 4, 6, 9, _lighten(color, 30))
    # Three wheels
    for wx, wy in [(cx - 4, cy + 4), (cx + 3, cy + 4), (cx, cy - 5)]:
        add_circle(px, wx, wy, 2, (40, 40, 44))
    # Gun barrel forward (up)
    for i in range(0, size // 3):
        if 0 <= cy - 4 - i < size:
            px[cy - 4 - i][cx] = (50, 50, 54, 255)


def detail_quad(px, size, color):
    """Quad: chunkier four-wheel bike with twin guns."""
    cx, cy = size // 2, size // 2
    add_rect_on(px, cx - 4, cy - 4, 8, 9, _lighten(color, 20))
    for wx in (cx - 5, cx + 4):
        for wy in (cy - 4, cy + 4):
            add_circle(px, wx, wy, 2, (38, 38, 42))
    # Twin barrels
    for bx in (cx - 2, cx + 2):
        for i in range(0, size // 3):
            if 0 <= cy - 4 - i < size and 0 <= bx < size:
                px[cy - 4 - i][bx] = (50, 50, 54, 255)


def detail_tank(px, size, color):
    """Tank: hull, tracks and a long forward turret barrel."""
    cx, cy = size // 2, size // 2
    # Tracks (sides)
    add_rect_on(px, 2, 4, 4, size - 8, (45, 45, 50))
    add_rect_on(px, size - 6, 4, 4, size - 8, (45, 45, 50))
    # Hull
    add_rect_on(px, 6, 6, size - 12, size - 12, _darken(color, 10))
    # Turret
    add_circle(px, cx, cy, size // 5, _lighten(color, 25))
    # Barrel forward (up)
    for i in range(0, size // 2):
        if 0 <= cy - i < size:
            for t in (-1, 0, 1):
                if 0 <= cx + t < size:
                    px[cy - i][cx + t] = (40, 40, 44, 255)


def detail_rocket_launcher(px, size, color):
    """Rocket launcher: tracked vehicle with an angled rocket pod."""
    cx, cy = size // 2, size // 2
    add_rect_on(px, 2, 4, 4, size - 8, (45, 45, 50))
    add_rect_on(px, size - 6, 4, 4, size - 8, (45, 45, 50))
    add_rect_on(px, 6, 8, size - 12, size - 12, _darken(color, 5))
    # Rocket pod (angled up-right): rows of tubes
    for r in range(3):
        for c in range(3):
            tx, ty = cx - 4 + c * 3, cy - 4 + r * 3
            if 0 <= tx < size and 0 <= ty < size:
                add_circle(px, tx, ty, 1, (210, 90, 60))


def detail_sniper(px, size, color):
    """Sniper: lone infantry with a long rifle."""
    cx = size // 2
    add_circle(px, cx, size // 4, 2, (220, 200, 170))  # head
    for y in range(size // 4 + 2, size // 2 + 3):
        if 0 <= y < size:
            px[y][cx] = (220, 200, 170, 255)
    # Long rifle pointing up-right
    for i in range(0, size // 2):
        bx, by = cx + i // 2, size // 3 - i // 2
        if 0 <= bx < size and 0 <= by < size:
            px[by][bx] = (60, 50, 40, 255)


def detail_helicopter(px, size, color):
    """Helicopter: fuselage with rotor blades and a tail."""
    cx, cy = size // 2, size // 2
    add_rect_on(px, cx - 3, cy - 2, 6, 8, _lighten(color, 15))  # body
    add_rect_on(px, cx - 1, cy + 5, 2, size // 3, _darken(color, 20))  # tail
    # Rotor blades (cross)
    add_rect_on(px, 2, cy - 5, size - 4, 2, (200, 200, 210))
    add_rect_on(px, cx - 1, 3, 2, size - 6, (200, 200, 210))
    add_circle(px, cx, cy - 4, 2, (60, 60, 66))  # rotor hub


def detail_jet_fighter(px, size, color):
    """Jet fighter: sleek delta wing pointing up."""
    cx = size // 2
    # Nose to tail body
    add_rect_on(px, cx - 2, 3, 4, size - 6, _lighten(color, 20))
    add_circle(px, cx, 4, 2, _lighten(color, 40))  # nose
    # Delta wings
    for i in range(0, size // 3):
        y = size // 2 + i
        half = size // 3 - i
        if half > 0 and 0 <= y < size:
            add_rect_on(px, cx - half, y, half * 2, 1, _darken(color, 10))
    # Tailfins
    add_rect_on(px, cx - 4, size - 6, 3, 3, _darken(color, 20))
    add_rect_on(px, cx + 2, size - 6, 3, 3, _darken(color, 20))


def detail_bomber(px, size, color):
    """Bomber: wide twin-engine aircraft."""
    cx = size // 2
    add_rect_on(px, cx - 3, 3, 6, size - 6, _lighten(color, 10))  # fuselage
    # Wide wings
    add_rect_on(px, 2, size // 2 - 2, size - 4, 5, _darken(color, 8))
    # Engines on wings
    add_circle(px, cx - size // 3, size // 2, 2, (50, 50, 56))
    add_circle(px, cx + size // 3, size // 2, 2, (50, 50, 56))
    # Nose + tail
    add_circle(px, cx, 4, 2, _lighten(color, 35))
    add_rect_on(px, cx - 3, size - 5, 6, 3, _darken(color, 20))


def gen_units(base_dir: str):
    for house_key, house_color in [("atreides", (0, 100, 200)), ("harkonnen", (200, 30, 30))]:
        gen_unit(base_dir, f"soldier_{house_key}.png", 20, house_color, detail_soldier)
        gen_unit(base_dir, f"harvester_{house_key}.png", 32, house_color, detail_harvester)
        gen_unit(base_dir, f"mcv_{house_key}.png", 36, house_color, detail_mcv)
        gen_unit(base_dir, f"trike_{house_key}.png", 24, house_color, detail_trike)
        gen_unit(base_dir, f"quad_{house_key}.png", 26, house_color, detail_quad)
        gen_unit(base_dir, f"tank_{house_key}.png", 34, house_color, detail_tank)
        gen_unit(base_dir, f"rocket_launcher_{house_key}.png", 32, house_color,
                 detail_rocket_launcher)
        gen_unit(base_dir, f"sniper_{house_key}.png", 18, house_color, detail_sniper)
        gen_unit(base_dir, f"helicopter_{house_key}.png", 34, house_color, detail_helicopter)
        gen_unit(base_dir, f"jet_fighter_{house_key}.png", 32, house_color, detail_jet_fighter)
        gen_unit(base_dir, f"bomber_{house_key}.png", 38, house_color, detail_bomber)


# ---------------------------------------------------------------------------
# UI TEXTURES
# ---------------------------------------------------------------------------
def gen_ui(base_dir: str):
    d = os.path.join(base_dir, "ui")

    # Sidebar background
    px = noisy_rect(220, 800, (30, 25, 20), noise=5)
    add_border(px, 220, 800, (60, 50, 40), thickness=2)
    save_png(os.path.join(d, "sidebar_bg.png"), 220, 800, px)

    # Minimap frame
    px = filled_rect(204, 204, (50, 45, 35))
    add_border(px, 204, 204, (100, 90, 70), thickness=2)
    save_png(os.path.join(d, "minimap_frame.png"), 204, 204, px)

    # Button normal
    px = noisy_rect(200, 36, (60, 55, 45), noise=5)
    add_border(px, 200, 36, (100, 90, 70), thickness=1)
    save_png(os.path.join(d, "button_normal.png"), 200, 36, px)

    # Button hover
    px = noisy_rect(200, 36, (80, 75, 60), noise=5)
    add_border(px, 200, 36, (140, 130, 100), thickness=1)
    save_png(os.path.join(d, "button_hover.png"), 200, 36, px)

    # Button pressed
    px = noisy_rect(200, 36, (40, 35, 28), noise=3)
    add_border(px, 200, 36, (80, 70, 55), thickness=1)
    save_png(os.path.join(d, "button_pressed.png"), 200, 36, px)

    # Selection box corner markers
    px = [[(0, 0, 0, 0) for _ in range(8)] for _ in range(8)]
    for i in range(8):
        px[0][i] = (0, 255, 0, 200)
        px[i][0] = (0, 255, 0, 200)
    save_png(os.path.join(d, "select_corner.png"), 8, 8, px)

    # Health bar segments
    for color_name, color_val in [("green", (0, 200, 0)), ("yellow", (200, 200, 0)),
                                   ("red", (200, 0, 0))]:
        px = filled_rect(32, 4, color_val)
        save_png(os.path.join(d, f"health_{color_name}.png"), 32, 4, px)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    script_dir = Path(__file__).parent.resolve()
    base_dir = str(script_dir / "assets" / "textures")

    random.seed(42)  # Reproducible textures

    print("=== Dune 2 Clone Texture Generator ===")
    print(f"Output: {base_dir}\n")

    print("[Terrain]")
    gen_terrain(base_dir)

    print("\n[Buildings]")
    gen_buildings(base_dir)

    print("\n[Units]")
    gen_units(base_dir)

    print("\n[UI]")
    gen_ui(base_dir)

    print(f"\nDone! All textures saved to {base_dir}")


if __name__ == "__main__":
    main()
