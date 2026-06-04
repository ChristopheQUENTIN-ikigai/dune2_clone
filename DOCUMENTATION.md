# Dune 2 Clone — Technical Documentation & API Reference

## 1. Overview

A Dune II real-time strategy clone built with Python 3.11+, Arcade 3.x, and SWI-Prolog (via Janus) for AI strategic reasoning.

**Stack:** Python 3.11 | Arcade 3.x | SWI-Prolog/Janus | JSON maps/saves

**Features:** 2 houses (Atreides/Harkonnen), 64×64 tile maps, scrollable/zoomable camera, minimap, A* pathfinding, production queues with building-construction progress, spice economy, Prolog AI (with Python fallback) that attacks in coordinated squadron waves, ground + flying units, splash-damage weapons, save/load with a file browser (F5/Shift+F5/F9), waypoint navigation, bullet projectiles, an in-game **Map Editor** and **Unit Editor**.

**Units:** Soldier, Sniper, Trike, Quad, Tank, Rocket Launcher, Helicopter, Jet Fighter, Bomber, Harvester, MCV.
**Buildings:** Construction Yard, Barracks, Refinery, Solar Plant, Light Factory, Heavy Factory, Hi-Tech, Airfield, Gun Turret.

---

## 2. Quick Start

```bash
pip install arcade>=3.0.0 janus-swi>=1.2.0
cd dune2_clone
python main.py
```

Textures auto-generate on first run. Janus/Prolog is optional — fallback Python AI works without it.

---

## 3. Controls (AZERTY-friendly)

### Menu
| Key | Action |
|-----|--------|
| Z / Up | Navigate up |
| S / Down | Navigate down |
| Enter / Space | Select |
| H | Help overlay |
| Escape | Exit game |

Menu items: **New Game**, **Load Game** (file browser over `saves/*.json`),
**Map Editor**, **Unit Editor**.

### In-Game
| Key | Action |
|-----|--------|
| Z Q S D / Arrows | Scroll camera |
| Mouse wheel | Zoom in/out |
| Left click unit | Select |
| Left click empty | Center camera on point |
| Left drag | Box select |
| Right click ground | Move selected units |
| Right click enemy | Attack target |
| Shift + Right click | Waypoint queue |
| X | Stop selected units |
| Space | Center on base |
| Ctrl + 1-5 | Set control group |
| 1-5 | Recall control group |
| M | Toggle minimap |
| Enter | Deploy MCV |
| F5 | Quick Save |
| Shift + F5 | Save to a new timestamped slot |
| F9 | Quick Load |
| H | Help overlay |
| Escape | Back to menu / Cancel |

### Map Editor
| Input | Action |
|-------|--------|
| Left click | Paint terrain / set P1 or P2 start (in start mode) |
| Right click | Erase to sand |
| Left drag | Continuous paint/erase |
| Z Q S D / Arrows | Scroll camera |
| Mouse wheel | Zoom |
| G | Toggle grid |
| Escape | Back to menu (cancels an open dialog first) |

Palette: terrain swatches, brush size (1/2/3/5), spice-per-tile stepper,
Set P1 / Set P2, grid toggle, filename field, Save / Load / New / Menu.

### Unit Editor
Click a unit in the left list, then use the +/- steppers (and the Flying
toggle) to change `cost`, `build_time`, `health`, `speed`, `attack_damage`,
`attack_range`, `attack_cooldown`, `size`. **Save** writes `config.json` and
updates in-memory stats; **Reload** discards unsaved edits; **Menu**/Escape
returns to the main menu.

---

## 4. Architecture

### 4.1 Directory Structure

```
dune2_clone/
├── main.py                    # Entry point, window, scene dispatch
├── config.json                # All editable constants
├── settings.py                # Loads config.json into Python constants
├── gen_textures.py            # Procedural PNG texture generator
├── requirements.txt
│
├── core/
│   ├── __init__.py            # EventBus
│   ├── game_state.py          # Central state: entities, players, commands
│   ├── player.py              # Player: credits, power, entity list
│   └── command.py             # Command dataclass + CommandType enum
│
├── map/
│   ├── __init__.py            # Tile dataclass
│   ├── game_map.py            # 64×64 grid, generation, JSON I/O
│   └── pathfinding.py         # A* on tile grid
│
├── entities/
│   ├── __init__.py            # Entity base class
│   ├── unit.py                # Unit base: movement, attack, waypoints
│   ├── soldier.py             # Soldier: light infantry
│   ├── harvester.py           # Harvester: spice collection cycle
│   ├── mcv.py                 # MCV: deploys into Construction Yard
│   ├── vehicle.py             # Vehicle(Unit): data-driven units (tank, trike,
│   │                          #   quad, rocket, sniper, air units) + make_unit()
│   └── building.py            # Building: production queue, power, construction
│
├── systems/
│   ├── movement_system.py     # A* pathing (flying units go straight), waypoints
│   ├── combat_system.py       # Attack logic, projectiles, splash damage
│   ├── production_system.py   # Build queue, construction timers, unit spawning
│   ├── resource_system.py     # Harvester AI, spice deposit
│   └── simulation.py          # Tick loop, command execution
│
├── ai/
│   ├── prolog_bridge.py       # Janus SWI-Prolog interface
│   ├── ai_controller.py       # Economy + coordinated squadron waves
│   └── strategy.pl            # Prolog knowledge base
│
├── ui/
│   ├── widgets.py             # TextInput, draw_button, point_in
│   └── file_browser.py        # Modal file picker overlay (saves/maps)
├── scenes/
│   ├── scene_manager.py       # Scene stack
│   ├── menu_scene.py          # Main menu (+ load browser)
│   ├── game_scene.py          # In-game rendering + input
│   ├── map_editor.py          # Terrain/spice/start-position editor
│   └── unit_editor.py         # Unit-stats editor (writes config.json)
│
├── save/
│   └── __init__.py            # Save/Load to JSON (+ timestamped slots)
│
├── assets/
│   ├── textures/{terrain,buildings,units,ui}/
│   └── maps/default.json
│
└── tests/
    ├── test_core.py           # core simulation
    ├── test_features.py       # construction, new units, flying, AI waves, save/load
    └── test_scenes.py         # editor & file-browser logic
```

### 4.2 Data Flow

```
Input → Command → CommandQueue → Simulation Tick → Systems → GameState → Renderer
                                      ↑
                              AI Controller (every 60 ticks)
                                      ↑
                              Prolog Engine (or fallback)
```

All state mutations go through `Command` objects. This makes the engine lockstep-ready for future multiplayer.

### 4.3 Coordinate System

The game uses a **Y-flipped** coordinate system:

- **Tile space:** `tiles[y][x]` where y=0 is the TOP row of the map
- **World space:** y=0 is the BOTTOM of the screen (Arcade convention)
- **Conversion:** `world_y = (MAP_HEIGHT - 1 - tile_y) * TILE_SIZE`

Helper functions in `entities/unit.py`:
```python
tile_to_world(tx, ty) -> (wx, wy)  # tile center in world pixels
world_to_tile(wx, wy) -> (tx, ty)  # world pixel to tile index
```

---

## 5. API Reference

### 5.1 `core.game_state.GameState`

Central state container.

| Field | Type | Description |
|-------|------|-------------|
| `tick` | int | Current simulation tick |
| `players` | dict[int, Player] | Player data by ID |
| `entities` | dict[int, Entity] | All entities by ID |
| `command_queue` | list[Command] | Pending commands |
| `next_entity_id` | int | Auto-increment counter |
| `game_over` | bool | Win condition met |
| `winner` | int or None | Winning player ID |

**Methods:**
- `new_entity_id() -> int`
- `add_entity(entity) -> int` — assigns ID, registers with player
- `remove_entity(entity_id)`
- `get_player_entities(player_id) -> list`
- `get_player_buildings(player_id) -> list`
- `get_player_units(player_id) -> list`
- `queue_command(command)`
- `get_commands_for_tick(tick) -> list[Command]`

### 5.2 `core.player.Player`

| Field | Type | Description |
|-------|------|-------------|
| `player_id` | int | 0=human, 1=AI |
| `house` | str | "atreides" or "harkonnen" |
| `is_ai` | bool | AI-controlled |
| `credits` | float | Current spice credits |
| `power_produced` | int | Total power output |
| `power_consumed` | int | Total power draw |

**Properties:** `power_balance`, `is_low_power`
**Methods:** `add_credits(amount)`, `spend_credits(amount) -> bool`

### 5.3 `core.command.Command`

| Field | Type | Description |
|-------|------|-------------|
| `tick` | int | Execution tick |
| `player_id` | int | Issuing player |
| `command_type` | CommandType | Action type |
| `entity_ids` | list[int] | Target entities |
| `target_x/y` | float | Tile coordinates |
| `target_entity_id` | int | Target entity for attack |
| `params` | dict | Extra: building_type, unit_type, waypoint |

**CommandType enum:** MOVE, ATTACK, ATTACK_MOVE, STOP, HARVEST, RETURN_HARVEST, BUILD_UNIT, PLACE_BUILDING, DEPLOY_MCV, SET_RALLY

### 5.4 `entities.unit.Unit`

| Field | Type | Description |
|-------|------|-------------|
| `x, y` | float | World pixel position |
| `tile_x, tile_y` | int (property) | Tile coords (Y-flipped) |
| `unit_type` | str | "soldier", "harvester", "mcv" |
| `speed` | float | Pixels per second |
| `attack_damage/range/cooldown` | | Combat stats |
| `state` | UnitState | IDLE/MOVING/ATTACKING/HARVESTING/RETURNING |
| `path` | list[tuple] | A* tile path |
| `waypoint_queue` | list[tuple] | Queued waypoints |
| `target_entity_id` | int | Attack target |

**Methods:**
- `set_path(path, preserve_state="")` — set path, optionally keep state
- `update_movement(dt) -> bool` — returns True when path complete
- `can_attack() -> bool`, `do_attack() -> int`
- `stop()`, `add_waypoint(tx, ty)`

**Module functions:**
- `tile_to_world(tx, ty) -> (wx, wy)`
- `world_to_tile(wx, wy) -> (tx, ty)`

### 5.5 `entities.building.Building`

| Field | Type | Description |
|-------|------|-------------|
| `building_type` | str | Config key |
| `tile_x, tile_y` | int | Top-left tile |
| `size_w, size_h` | int | Size in tiles |
| `power` | int | Power contribution |
| `producing` | str or None | Current production item |
| `production_queue` | list[str] | Up to 5 queued items |
| `production_progress` | float (property) | 0.0 to 1.0 |
| `attack_damage / attack_range / attack_cooldown` | | Defensive-structure combat stats (0 for normal buildings) |

**Footprint coordinates (single source of truth).** The map is Y-flipped (`tiles[y][x]` row 0 is the top; world y increases upward). A building's `world_left`/`world_bottom` give its footprint's bottom-left world corner and `pixel_x`/`pixel_y` give its footprint centre, with `world_bottom = (MAP_HEIGHT - tile_y - size_h) * TILE_SIZE`. Rendering, mouse-picking, the placement ghost, combat aim and the harvester drop-off check all use these same properties, so they cannot disagree (a bug that previously existed when each computed its own convention).

**Methods:**
- `create(building_type, owner_id, tx, ty) -> Building` (classmethod) — also seeds the Entity world position from the footprint centre and loads any `attack_*` stats
- `get_producible() -> list[str]`
- `start_production(item, build_time)`
- `queue_production(item) -> bool`
- `update_production(dt) -> Optional[str]` — returns completed item
- `start_next_in_queue() -> Optional[str]`
- `is_combat` / `can_attack()` / `do_attack()` / `update_attack(dt)` — defensive-structure firing

### 5.6 `map.game_map.GameMap`

| Method | Description |
|--------|-------------|
| `get_tile(x, y) -> Tile` | Get tile at coords |
| `is_passable(tx, ty) -> bool` | Not mountain, no building |
| `is_buildable(tx, ty) -> bool` | Rock terrain, no building |
| `can_place_building(tx, ty, w, h) -> bool` | All tiles buildable |
| `place_building_tiles(tx, ty, w, h, id)` | Mark tiles occupied |
| `find_spawn_tile(btx, bty, bw, bh) -> (tx, ty)` | Find passable spawn |
| `find_nearest_spice(tx, ty) -> (tx, ty)` | Nearest spice tile |
| `find_nearest_refinery(tx, ty, pid, gs) -> int` | Nearest refinery ID |
| `generate_default()` | Procedural map generation |
| `save_to_json(path)` / `load_from_json(path)` | JSON I/O |

### 5.7 `map.pathfinding`

```python
astar(game_map, start, goal, max_iterations=2000) -> list[tuple] | None
```
Returns list of `(tx, ty)` tile waypoints, or None if no path. 8-directional movement, diagonal requires both cardinal tiles passable.

### 5.8 `systems.simulation.Simulation`

Main game loop. Constructed with `(game_state, game_map)`.

- `update(dt)` — accumulates time, runs ticks at `TICK_RATE` Hz
- Each tick: process commands → movement → combat → production → resources → win check

### 5.9 `systems.production_system.ProductionSystem`

- `request_unit_production(building, unit_type) -> bool` — starts or queues
- `start_building_placement(pid, btype, tx, ty) -> bool` — validates and places
- `update(dt)` — advances timers, spawns completed units, auto-starts queued

### 5.10 `systems.combat_system.CombatSystem`

- `issue_attack(attacker, target_id)` — sets attack state
- `update(dt, entities)` — chase, range check, fire, projectile flight, damage
- `_update_building_combat(turret, entities)` — defensive structures (e.g. Gun Turret) re-acquire the nearest enemy unit in range each tick and fire without moving; they ignore enemy buildings
- `projectiles: list[Projectile]` — active bullet visuals

All combat uses world-space positions; for a building the aim point is its footprint centre (`pixel_x`/`pixel_y`), the same spot the renderer and picking use.

### 5.11 `systems.resource_system.ResourceSystem`

Manages harvester state machine: IDLE → HARVESTING → RETURNING → IDLE cycle. Only harvests on `spice` or `thick_spice` terrain tiles.

### 5.12 `ai.prolog_bridge.PrologBridge`

- `assert_game_state(gs, pid, map)` — pushes facts to Prolog
- `query_decisions() -> list[(action, target)]`
- `query_strategy() -> str`

Falls back gracefully if Janus unavailable.

### 5.13 `ai.ai_controller.AIController`

- `update()` — runs every `AI_DECISION_INTERVAL` ticks: a build/produce brain
  (Prolog or Python fallback) followed by `_manage_squadrons()`.
- `COMBAT_TYPES` / `is_combat_unit(e)` — derived from config; any unit with
  `attack_damage > 0` that is not a harvester/MCV is wave-eligible.
- Economy: `_economy_buildout()` walks the tech tree (turrets → light factory →
  heavy factory → hi-tech → airfield) gated by credits; `_do_build` avoids
  duplicate buildings; `_do_produce` requires a built, capable factory.
- **Squadron waves** (`_manage_squadrons`): newly built combat units gather at a
  rally tile (`_rally_tile`, between the AI base and the enemy). When the
  squad reaches a threshold (grows with `waves_launched`, lower when
  `aggressive`), all units are issued one shared ATTACK order and recorded as a
  wave in `self.waves`. Dead members are pruned each cycle; a wave whose target
  fell is re-targeted via `_pick_target` (enemy CY → nearest building → nearest
  unit). If the base is threatened (`_nearest_threat` within `DEFEND_RADIUS`),
  the still-gathering squad is redirected to defend.

### 5.14 `save` module

- `save_game(game_state, game_map, filepath=None) -> str`
- `load_game(filepath=None) -> (GameState, map_tiles) | (None, None)`
- `timestamped_save_path() -> str` — `saves/save_YYYYmmdd_HHMMSS.json` (Shift+F5)
- `quicksave_exists() -> bool`

### 5.15 `scenes.game_scene.GameScene` rendering

The world is drawn with GPU-batched `arcade.SpriteList`s under an `arcade.Camera2D`, rather than per-tile/per-entity immediate-mode calls:

- **Three sprite layers** — `terrain_list` (one sprite per tile, built once), `building_list`, and `unit_list` — are each drawn in a single batched call inside `with world_cam.activate():`.
- **Camera mapping** matches the screen-space helper `_w2s` exactly: each frame `world_cam.position = (cam_x + W/(2*zoom), cam_y + H/(2*zoom))` and `world_cam.zoom = zoom`. On window resize the camera is recreated so it adopts the new viewport. Because the mapping is identical, all overlays stay in screen space.
- **Overlays** (building labels, HP bars, selection outlines, production bars, harvester load bars, rally circles, projectiles, sidebar, HUD, minimap) are drawn after the camera block using `_w2s`, so they line up with the sprites.
- **Incremental updates** — `_sync_entity_sprites()` adds sprites for new entities, repositions moving units, and drops sprites for dead entities each frame; buildings are static so they are positioned once. `_update_terrain_sprites()` only swaps textures for spice tiles that deplete to sand, and a tile leaves the watch list once converted (depletion is one-way).
- **Fallback** — if a texture is missing, a small solid-colour texture (house/terrain colour) is used so every entity still has a sprite; the building/unit base shape is then just that colour and the overlays still draw on top. Building textures are authored at footprint resolution (`size_tiles × TILE_SIZE` px).
- **Data-driven build menu** — `_draw_sidebar` registers each drawn button's rect in `_sidebar_buttons`, and `_sidebar_click` hit-tests that same list, so the menu reflects every owned building's `produces` list and the draw/click layouts can never drift apart.

---

## 6. Configuration (config.json)

All gameplay constants are editable without code changes:

- **Window:** resolution, vsync, fps cap
- **Camera:** scroll speed, edge margin, zoom range
- **Buildings:** cost, build time, health, power, size, produces list
- **Units:** cost, build time, health, speed, damage, range, cooldown
- **Keybindings:** AZERTY/QWERTY key mappings
- **Terrain:** RGB colors for each tile type

### Building Production Rules

| Building | Produces | Notes |
|----------|----------|-------|
| Construction Yard | Barracks, Refinery, Solar Plant, Heavy Factory, Gun Turret | placement-based |
| Barracks | Soldier | |
| Refinery | Harvester | also the spice drop-off point |
| Solar Plant | (nothing) | +50 power |
| Heavy Factory | Harvester, MCV | the MCV deploys back into a Construction Yard, so this is how you expand to a new base |
| Gun Turret | (nothing) | defensive structure: auto-fires on the nearest enemy *unit* within range (does not chase, does not target enemy buildings) |

The Construction Yard's `produces` list is what drives the in-game sidebar build menu, which is generated dynamically from each owned building's `produces` list — adding an entry there makes it appear (and be clickable) with no UI code changes.

---

## 7. Prolog AI Knowledge Base (strategy.pl)

Dynamic facts asserted per decision cycle:
```prolog
my_credits(N).
my_power(Used, Total).
my_building(Type, X, Y, Health).
my_unit(Type, X, Y, Health).
enemy_building(Type, X, Y, Health).
enemy_unit(Type, X, Y, Health).
spice_field(X, Y, Amount).
```

Decision rules return:
```prolog
decision(build, barracks).
decision(produce, soldier).
decision(attack, all).
decision(defend, base).
```

Strategy assessment: `recommend_strategy(S)` → economy | expand | military | attack | defend

---

## 8. Save File Format

JSON at `saves/quicksave.json`:
```json
{
  "tick": 1500,
  "next_entity_id": 42,
  "players": { "0": { "house": "atreides", "credits": 3200, ... } },
  "entities": [ { "type": "soldier", "entity_id": 5, "x": 480, "y": 1600, ... } ],
  "map_tiles": [ { "x": 10, "y": 15, "terrain": "spice", "spice": 1200 } ]
}
```

---

## 9. Extending

### Adding a New Unit Type
1. Add stats to `config.json` → `units`. Recognised fields: `cost`, `build_time`,
   `health`, `speed`, `attack_damage`, `attack_range`, `attack_cooldown`,
   `size`, `category` (`infantry`/`vehicle`/`air`/`support`), and optionally
   `flying: true` and `splash` (tiles).
2. **No new class is needed** for a normal combat/vehicle/air unit:
   `entities.vehicle.make_unit()` constructs a `Vehicle(Unit)` for any type that
   isn't Soldier/Harvester/MCV, reading every stat from config. Only add a
   dedicated subclass for bespoke behaviour (as Harvester/MCV do).
3. Add a detail function + a `gen_unit(...)` call in `gen_textures.py`, then run
   `python gen_textures.py` to emit `<type>_atreides.png` / `<type>_harkonnen.png`.
4. Add the type to the relevant building's `produces` list in config.
5. `flying` units automatically path in straight lines (movement_system) and
   `splash` weapons automatically apply area damage (combat_system). Save/load
   already handles any unit produced by `make_unit`.
6. You can also adjust any existing unit's numbers live with the in-game
   **Unit Editor**, which writes back to `config.json`.

### Adding a New Building
1. Add to `config.json` → `buildings` with its stats and `produces` list (and, for a defensive structure, `attack_damage` / `attack_range` / `attack_cooldown`).
2. Add a texture in `gen_textures.py`, sized `size_w*TILE_SIZE` × `size_h*TILE_SIZE` px (the renderer expects building textures at footprint resolution), then regenerate.
3. Add it to a producing building's `produces` list (e.g. the Construction Yard) so it appears in the build menu.

The sidebar build menu, per-building production/queue logic, **construction
progress** (timer → `built` flag → power applied on completion) and unit
spawning are all data-driven, so a new building needs no UI or production code
changes, and a new unit it produces needs none either (see above). Bespoke
behaviour (e.g. the Gun Turret's targeting) lives in code — the Turret reuses
the generic combat path in `combat_system._update_building_combat`, driven by
the `attack_*` config fields, and is gated on `built` so it can't fire while
under construction.

### Map Editor & Unit Editor
- `scenes/map_editor.py` edits a `GameMap` in place (terrain, per-tile spice,
  the two start positions) and round-trips through `GameMap.save_to_json` /
  `load_from_json`. Maps live in `assets/maps/`.
- `scenes/unit_editor.py` edits a working copy of `UNIT_STATS` and, on Save,
  rewrites `config.json` **and** mutates the in-memory `settings.UNIT_STATS`
  dicts in place so changes apply to units built later in the same session.
- Both reuse `ui/widgets.py` (TextInput, buttons) and `ui/file_browser.py`
  (a modal picker that lists files by glob, newest first).

### Adding Fog of War (planned)
- Track `explored[y][x]` and `visible[y][x]` per player
- Only render visible tiles; dim explored-but-not-visible
- Update visibility each tick based on unit sight ranges
