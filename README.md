# Dune 2 Clone

A real-time strategy game inspired by Dune II: The Battle for Arrakis.
Built with Python 3.11+, Arcade 3.x, and (optionally) SWI-Prolog via Janus for AI.

## Quick Start

```bash
pip install "arcade>=3.0.0,<4.0.0"          # janus-swi is optional (AI fallback exists)
cd dune2_clone
python main.py
```

Textures and the default map are auto-generated on first run. If `janus-swi` /
SWI-Prolog is not installed, the game automatically uses the built-in Python AI.

## Controls (AZERTY-friendly)

### Menu
- Z/Up, S/Down — navigate, Enter/Space — select
- H — help, Escape — exit
- **New Game** — start a skirmish vs the AI
- **Load Game** — open a file browser and pick any saved `.json`
- **Map Editor** — paint terrain, place spice, set start positions, save/load maps
- **Unit Editor** — tweak unit stats (cost, hp, speed, damage…) and save to config

### In-Game
- ZQSD / Arrows — scroll camera, Mouse wheel — zoom
- Left click — select, Left drag — box select
- Right click — move/attack, Shift+Right click — queue waypoints
- X — stop units, Space — center base
- Ctrl+1-5 — set control group, 1-5 — recall group
- M — minimap, H — help, Enter — deploy MCV
- **F5 — quick save, Shift+F5 — save to a new timestamped slot, F9 — quick load**
- Escape — back to menu

### Map Editor
- Left click — paint current terrain (or set a start position in P1/P2 mode)
- Right click — erase to sand, brush sizes 1/2/3/5
- G — toggle grid, mouse wheel — zoom, ZQSD/Arrows — scroll
- Type a name and press **Save**; **Load** opens a map browser

## Units & Buildings

**Buildings** — Construction Yard ➜ Barracks, Refinery, Solar Plant,
Light Factory, Heavy Factory, Hi-Tech, Airfield, Gun Turret.

**Production**
- Barracks ➜ Soldier, Sniper
- Refinery ➜ Harvester
- Light Factory ➜ Trike, Quad
- Heavy Factory ➜ Harvester, MCV, Tank, Rocket Launcher
- Hi-Tech ➜ Helicopter
- Airfield ➜ Jet Fighter, Bomber

**Air units** (Helicopter, Jet Fighter, Bomber) fly in straight lines over any
terrain, ignoring mountains and water. **Rocket Launchers** and **Bombers**
deal splash damage. Every building under construction shows an animated
progress bar and only becomes functional (and supplies power) once finished.

## AI

The AI builds out a full economy and tech tree, then groups its combat units
into **squadrons** at a rally point and launches them as **coordinated waves**
against a shared objective (preferring your Construction Yard). It keeps
multiple waves in flight, re-targets a wave when its objective is destroyed,
and pulls the gathering squad back to defend when its base is threatened.

## Configuration

All constants live in `config.json` — resolution, keybindings, unit stats,
costs, speeds, building stats and production rules. The in-game Unit Editor
writes to this file.

## Architecture

- Lockstep-ready simulation (Command objects, deterministic fixed ticks)
- Optional Prolog AI via Janus, with a complete Python fallback AI
- Scene-based (Menu, Game, Map Editor, Unit Editor); JSON maps (64×64)
- World rendered with batched SpriteLists under a Camera2D; HUD in screen space

## Testing

```bash
python tests/test_core.py        # core simulation
python tests/test_features.py    # construction, new units, flying, AI waves, save/load
python tests/test_scenes.py      # editor & file-browser logic
```

See `DOCUMENTATION.md` for the full technical reference and API.
