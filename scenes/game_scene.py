"""
Game scene — all features working:
- F5 save, F9 load
- Left click empty = center camera
- Production queue in sidebar
- Spawn overlap check at game start
- Hover info
- Bullets, waypoints, ctrl+groups
"""
import math
import arcade
from scenes.scene_manager import Scene
from core.game_state import GameState
from core.player import Player
from core.command import Command, CommandType
from map.game_map import GameMap
from map import Tile
from entities.building import Building
from entities.unit import Unit, UnitState, tile_to_world, world_to_tile
from entities.soldier import Soldier
from entities.harvester import Harvester
from entities.mcv import MCV
from systems.simulation import Simulation
from ai.ai_controller import AIController
from save import save_game, load_game, get_quicksave_path, timestamped_save_path
from settings import (
    TILE_SIZE, MAP_WIDTH, MAP_HEIGHT, MAP_PIXEL_WIDTH, MAP_PIXEL_HEIGHT,
    SIDEBAR_WIDTH, MINIMAP_WIDTH, MINIMAP_HEIGHT,
    SCROLL_SPEED, EDGE_SCROLL_MARGIN, EDGE_SCROLL_SPEED,
    ZOOM_MIN, ZOOM_MAX, ZOOM_STEP,
    HOUSES, TERRAIN_COLORS, BUILDING_STATS, UNIT_STATS, STARTING_CREDITS,
    TEXTURES_PATH
)

class GameScene(Scene):
    def __init__(self, window, load_save=False, save_path=None):
        super().__init__(window)
        self.cam_x = self.cam_y = 0.0
        self.zoom = 1.0
        self.keys_held = set()
        self.mouse_x = self.mouse_y = 0.0
        self.drag_start = None
        self.dragging = False
        self.show_help = False
        self.placing_building = ""
        self.show_minimap = True
        self.game_state = GameState()
        self.game_map = GameMap()
        self.simulation = None
        self.ai_controller = None
        self.terrain_textures = {}
        self.building_textures = {}
        self.unit_textures = {}
        self.selected_ids = []
        self.control_groups = {}
        self._text_cache = {}
        self.hover_info = ""
        self.notification = ""
        self.notif_timer = 0.0
        self._load_save = load_save
        self._save_path = save_path
        # --- Batched rendering (SpriteList + Camera2D) ---
        # The world (terrain + buildings + units) is drawn through GPU-batched
        # SpriteLists under a Camera2D instead of per-object immediate-mode
        # draw calls. Overlays (labels, HP bars, selection, production, rally,
        # projectiles, sidebar, minimap, HUD) stay in screen space and are
        # positioned with _w2s, which the camera mapping matches exactly.
        self.world_cam = None
        self.terrain_list = None
        self.building_list = None
        self.unit_list = None
        self._bld_sprites = {}       # entity_id -> Sprite (buildings; static)
        self._unit_sprites = {}      # entity_id -> Sprite (units; repositioned per frame)
        self._terrain_sprites = {}   # (tx,ty) -> Sprite, only for tiles that can mutate
        self._mutable_tiles = []     # (tx,ty) of spice tiles still able to change terrain
        self._terrain_cache = {}     # (tx,ty) -> last terrain string for mutable tiles
        self._fallback_tex = {}      # color tuple -> solid arcade.Texture
        self._sidebar_buttons = []   # clickable build-menu rects (shared by draw + click)

    def on_show(self):
        arcade.set_background_color((30, 25, 15))
        self._load_textures()
        if self._load_save:
            self._do_load()
        else:
            self._setup_new_game()

    def _load_textures(self):
        tp = TEXTURES_PATH
        for tn in TERRAIN_COLORS:
            p = tp / "terrain" / f"{tn}.png"
            if p.exists(): self.terrain_textures[tn] = arcade.load_texture(str(p))
        for house in ("atreides", "harkonnen"):
            for bt in BUILDING_STATS:
                p = tp / "buildings" / f"{bt}_{house}.png"
                if p.exists(): self.building_textures[f"{bt}_{house}"] = arcade.load_texture(str(p))
            for ut in UNIT_STATS:
                p = tp / "units" / f"{ut}_{house}.png"
                if p.exists(): self.unit_textures[f"{ut}_{house}"] = arcade.load_texture(str(p))

    def _notify(self, msg):
        self.notification = msg
        self.notif_timer = 3.0

    # === BATCHED RENDER LISTS ===
    def _solid_tex(self, color):
        """A small solid-color texture, used as a fallback when a sprite's
        real texture is missing so every entity still has a SpriteList sprite
        (its base shape is then simply the house/terrain colour)."""
        key = tuple(color)
        t = self._fallback_tex.get(key)
        if t is None:
            from PIL import Image
            rgba = key if len(key) == 4 else (key[0], key[1], key[2], 255)
            t = arcade.Texture(Image.new("RGBA", (8, 8), rgba))
            self._fallback_tex[key] = t
        return t

    def _make_terrain_sprite(self, terrain, cx, cy):
        tex = self.terrain_textures.get(terrain) or self._solid_tex(
            TERRAIN_COLORS.get(terrain, (200, 180, 120)))
        sp = arcade.Sprite(tex, center_x=cx, center_y=cy)
        sp.width = TILE_SIZE
        sp.height = TILE_SIZE
        return sp

    def _build_render_lists(self):
        """Create the Camera2D and SpriteLists. Terrain is built once (one
        sprite per tile); only spice tiles (which can deplete to sand) are
        tracked for later texture swaps. Building/unit lists start empty and
        are populated by _sync_entity_sprites each frame."""
        self.world_cam = arcade.Camera2D()
        self.terrain_list = arcade.SpriteList()
        self._terrain_sprites = {}
        self._mutable_tiles = []
        self._terrain_cache = {}
        for ty in range(MAP_HEIGHT):
            row = self.game_map.tiles[ty]
            for tx in range(MAP_WIDTH):
                tile = row[tx]
                cx = tx * TILE_SIZE + TILE_SIZE / 2
                cy = (MAP_HEIGHT - 1 - ty) * TILE_SIZE + TILE_SIZE / 2
                sp = self._make_terrain_sprite(tile.terrain, cx, cy)
                self.terrain_list.append(sp)
                if tile.terrain in ("spice", "thick_spice"):
                    self._terrain_sprites[(tx, ty)] = sp
                    self._mutable_tiles.append((tx, ty))
                    self._terrain_cache[(tx, ty)] = tile.terrain
        self.building_list = arcade.SpriteList()
        self.unit_list = arcade.SpriteList()
        self._bld_sprites = {}
        self._unit_sprites = {}

    def _update_terrain_sprites(self):
        """Swap terrain textures for spice tiles that have changed (spice->sand).
        Depletion is one-way, so a tile leaves the watch list once it is sand."""
        if not self._mutable_tiles:
            return
        still = []
        for (tx, ty) in self._mutable_tiles:
            terr = self.game_map.tiles[ty][tx].terrain
            if terr != self._terrain_cache.get((tx, ty)):
                self._terrain_cache[(tx, ty)] = terr
                sp = self._terrain_sprites.get((tx, ty))
                if sp is not None:
                    sp.texture = self.terrain_textures.get(terr) or self._solid_tex(
                        TERRAIN_COLORS.get(terr, (200, 180, 120)))
            if terr in ("spice", "thick_spice"):
                still.append((tx, ty))
        self._mutable_tiles = still

    def _sync_entity_sprites(self):
        """Add sprites for new entities, reposition moving units, and drop
        sprites for dead entities. Buildings are static so they are positioned
        once at creation; units are repositioned every frame."""
        ents = self.game_state.entities
        alive_b = set()
        for e in ents.values():
            if isinstance(e, Building) and e.alive:
                alive_b.add(e.entity_id)
                if e.entity_id not in self._bld_sprites:
                    house = self.game_state.players[e.owner_id].house
                    tex = self.building_textures.get(f"{e.building_type}_{house}") \
                        or self._solid_tex(HOUSES[house]["color"])
                    sp = arcade.Sprite(tex, center_x=e.pixel_x, center_y=e.pixel_y)
                    sp.width = e.size_w * TILE_SIZE
                    sp.height = e.size_h * TILE_SIZE
                    self._bld_sprites[e.entity_id] = sp
                    self.building_list.append(sp)
        for eid in [i for i in self._bld_sprites if i not in alive_b]:
            self._bld_sprites.pop(eid).remove_from_sprite_lists()

        alive_u = set()
        for e in ents.values():
            if isinstance(e, Unit) and e.alive:
                alive_u.add(e.entity_id)
                sp = self._unit_sprites.get(e.entity_id)
                if sp is None:
                    house = self.game_state.players[e.owner_id].house
                    tex = self.unit_textures.get(f"{e.unit_type}_{house}") \
                        or self._solid_tex(HOUSES[house]["color"])
                    sp = arcade.Sprite(tex, center_x=e.x, center_y=e.y)
                    sp.width = e.size
                    sp.height = e.size
                    self._unit_sprites[e.entity_id] = sp
                    self.unit_list.append(sp)
                else:
                    sp.center_x = e.x
                    sp.center_y = e.y
        for eid in [i for i in self._unit_sprites if i not in alive_u]:
            self._unit_sprites.pop(eid).remove_from_sprite_lists()


    # === SAVE / LOAD ===
    def _do_save(self, as_slot=False):
        if as_slot:
            path = save_game(self.game_state, self.game_map, timestamped_save_path())
            import os
            self._notify(f"Saved slot: {os.path.basename(path)}")
        else:
            save_game(self.game_state, self.game_map)
            self._notify("Game saved!")

    def _do_load(self):
        gs, map_tiles = load_game(self._save_path)
        if gs is None:
            self._notify("No save found!")
            self._setup_new_game()
            return
        self.game_state = gs
        self.game_map = GameMap()
        self.game_map._init_empty()
        if map_tiles:
            for td in map_tiles:
                x, y = td["x"], td["y"]
                if 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT:
                    self.game_map.tiles[y][x] = Tile(x=x, y=y, terrain=td["terrain"], spice=td.get("spice", 0))
        # Rebuild building tiles on map
        for e in self.game_state.entities.values():
            if isinstance(e, Building):
                s = BUILDING_STATS[e.building_type]["size_tiles"]
                self.game_map.place_building_tiles(e.tile_x, e.tile_y, s[0], s[1], e.entity_id)
        self.simulation = Simulation(self.game_state, self.game_map)
        ai_pid = [p for p in self.game_state.players if self.game_state.players[p].is_ai]
        self.ai_controller = AIController(self.game_state, self.game_map, ai_pid[0] if ai_pid else 1)
        # Center on player base
        blds = self.game_state.get_player_buildings(0)
        if blds:
            b = blds[0]
            wx, wy = tile_to_world(b.tile_x + b.size_w//2, b.tile_y + b.size_h//2)
            self.cam_x = wx - self.window.width/(2*self.zoom)
            self.cam_y = wy - self.window.height/(2*self.zoom)
        self._clamp_camera()
        self._build_render_lists()
        self._notify("Game loaded!")

    # === NEW GAME ===
    def _setup_new_game(self):
        self.game_map.generate_default()
        self.game_state.players[0] = Player(0, "atreides", False, STARTING_CREDITS)
        self.game_state.players[1] = Player(1, "harkonnen", True, STARTING_CREDITS)
        self.simulation = Simulation(self.game_state, self.game_map)
        sp0 = self.game_map.starting_positions[0]
        sp1 = self.game_map.starting_positions[1]
        self._spawn_base(0, sp0["x"], sp0["y"])
        self._spawn_base(1, sp1["x"], sp1["y"])
        self._fix_unit_overlaps()
        self.ai_controller = AIController(self.game_state, self.game_map, 1)
        wx, wy = tile_to_world(sp0["x"]+3, sp0["y"]+3)
        self.cam_x = wx - self.window.width/(2*self.zoom)
        self.cam_y = wy - self.window.height/(2*self.zoom)
        self._clamp_camera()
        self._build_render_lists()

    def _spawn_base(self, pid, tx, ty):
        player = self.game_state.players[pid]
        def place_b(btype, bx, by):
            b = Building.create(btype, pid, bx, by)
            eid = self.game_state.add_entity(b)
            s = BUILDING_STATS[btype]["size_tiles"]
            self.game_map.place_building_tiles(bx, by, s[0], s[1], eid)
            pw = BUILDING_STATS[btype]["power"]
            player.power_produced += max(0, pw)
            player.power_consumed += abs(min(0, pw))
            return eid, s
        _, cys = place_b("construction_yard", tx, ty)
        _, rs = place_b("refinery", tx+4, ty)
        place_b("solar_plant", tx, ty+4)
        place_b("barracks", tx+4, ty+3)
        # Harvester
        stx, sty = self.game_map.find_spawn_tile(tx+4, ty, rs[0], rs[1])
        wx, wy = tile_to_world(stx, sty)
        self.game_state.add_entity(Harvester(owner_id=pid, x=wx, y=wy))
        # 3 soldiers at different spawn tiles
        for i in range(3):
            stx2, sty2 = self.game_map.find_spawn_tile(tx, ty, cys[0], cys[1])
            swx, swy = tile_to_world(stx2 + i % 3, sty2 + i // 3)
            self.game_state.add_entity(Soldier(owner_id=pid, x=swx, y=swy))

    def _fix_unit_overlaps(self):
        """After spawning, nudge any units sitting on building tiles."""
        for e in list(self.game_state.entities.values()):
            if not isinstance(e, Unit) or not e.alive:
                continue
            tx, ty = e.tile_x, e.tile_y
            tile = self.game_map.get_tile(tx, ty)
            if tile and not tile.passable:
                # Find nearest passable tile
                for r in range(1, 8):
                    found = False
                    for dx in range(-r, r+1):
                        for dy in range(-r, r+1):
                            ntx, nty = tx+dx, ty+dy
                            if self.game_map.is_passable(ntx, nty):
                                e.x, e.y = tile_to_world(ntx, nty)
                                found = True; break
                        if found: break
                    if found: break

    # === UPDATE ===
    def on_update(self, dt):
        if self.game_state.game_over: return
        if self.notif_timer > 0: self.notif_timer -= dt
        scroll = SCROLL_SPEED * dt / self.zoom
        if arcade.key.Z in self.keys_held or arcade.key.UP in self.keys_held: self.cam_y += scroll
        if arcade.key.S in self.keys_held or arcade.key.DOWN in self.keys_held: self.cam_y -= scroll
        if arcade.key.Q in self.keys_held or arcade.key.LEFT in self.keys_held: self.cam_x -= scroll
        if arcade.key.D in self.keys_held or arcade.key.RIGHT in self.keys_held: self.cam_x += scroll
        m = EDGE_SCROLL_MARGIN; es = EDGE_SCROLL_SPEED * dt / self.zoom
        gar = self.window.width - SIDEBAR_WIDTH
        if self.mouse_x < gar:
            if self.mouse_x < m: self.cam_x -= es
            elif self.mouse_x > gar - m: self.cam_x += es
            if self.mouse_y < m: self.cam_y -= es
            elif self.mouse_y > self.window.height - m: self.cam_y += es
        self._clamp_camera()
        self.simulation.update(dt)
        self.ai_controller.update()
        self.selected_ids = [e for e in self.selected_ids if e in self.game_state.entities and self.game_state.entities[e].alive]
        self._update_hover()

    def _update_hover(self):
        if self.mouse_x > self.window.width - SIDEBAR_WIDTH: return
        wx, wy = self._s2w(self.mouse_x, self.mouse_y)
        tx, ty = world_to_tile(wx, wy)
        tile = self.game_map.get_tile(tx, ty)
        if not tile: self.hover_info = ""; return
        info = f"({tx},{ty}) {tile.terrain}"
        if tile.has_spice: info += f" spice:{int(tile.spice)}"
        if tile.building_id >= 0:
            b = self.game_state.entities.get(tile.building_id)
            if b and isinstance(b, Building):
                info += f" | {BUILDING_STATS.get(b.building_type,{}).get('name','?')}"
        for e in self.game_state.entities.values():
            if isinstance(e, Unit) and e.alive:
                sx, sy = self._w2s(e.x, e.y)
                if abs(sx-self.mouse_x) < e.size*self.zoom and abs(sy-self.mouse_y) < e.size*self.zoom:
                    info += f" | {UNIT_STATS.get(e.unit_type,{}).get('name','?')} HP:{e.health}"
                    break
        self.hover_info = info

    def _clamp_camera(self):
        mx = MAP_PIXEL_WIDTH - (self.window.width-SIDEBAR_WIDTH)/self.zoom
        my = MAP_PIXEL_HEIGHT - self.window.height/self.zoom
        self.cam_x = max(0, min(self.cam_x, max(0, mx)))
        self.cam_y = max(0, min(self.cam_y, max(0, my)))

    def _w2s(self, wx, wy): return (wx-self.cam_x)*self.zoom, (wy-self.cam_y)*self.zoom
    def _s2w(self, sx, sy): return sx/self.zoom+self.cam_x, sy/self.zoom+self.cam_y

    # === DRAWING ===
    def on_draw(self):
        self.window.clear()
        self._draw_world()
        self._draw_projectiles()
        self._draw_sidebar()
        self._draw_hud()
        if self.show_minimap: self._draw_minimap()
        if self.dragging and self.drag_start: self._draw_selection_box()
        if self.placing_building: self._draw_building_ghost()
        if self.show_help: self._draw_help()
        if self.game_state.game_over: self._draw_game_over()
        if self.notif_timer > 0:
            arcade.draw_text(self.notification, self.window.width/2-SIDEBAR_WIDTH/2, 60,
                             (255,255,100,int(min(1,self.notif_timer)*255)), 16,
                             anchor_x="center", font_name="Courier New", bold=True)

    def _draw_world(self):
        if self.world_cam is None:
            return
        # Keep batched data current, then draw all three world layers under the
        # camera in three GPU-batched calls (was a Python loop over every tile
        # and entity each frame).
        self._update_terrain_sprites()
        self._sync_entity_sprites()
        z = self.zoom
        self.world_cam.position = (self.cam_x + self.window.width/(2*z),
                                   self.cam_y + self.window.height/(2*z))
        self.world_cam.zoom = z
        with self.world_cam.activate():
            self.terrain_list.draw()
            self.building_list.draw()
            self.unit_list.draw()
        # Screen-space overlays (camera mapping == _w2s, so they align exactly).
        for e in self.game_state.entities.values():
            if isinstance(e, Building) and e.alive: self._draw_building_overlay(e)
        for e in self.game_state.entities.values():
            if isinstance(e, Unit) and e.alive: self._draw_unit_overlay(e)
        for e in self.game_state.entities.values():
            if isinstance(e, Building) and e.alive and e.producing:
                stx,sty = self.game_map.find_spawn_tile(e.tile_x, e.tile_y, e.size_w, e.size_h)
                swx,swy = tile_to_world(stx,sty)
                sx,sy = self._w2s(swx,swy)
                arcade.draw_circle_outline(sx, sy, 8*self.zoom, (0,255,0,120), 2)

    def _draw_building_overlay(self, b):
        # Footprint corner (world_left/world_bottom) matches the building sprite,
        # so the label, HP bar, selection box and production bar sit correctly.
        sx,sy = self._w2s(b.world_left, b.world_bottom)
        w = b.size_w*TILE_SIZE*self.zoom; h = b.size_h*TILE_SIZE*self.zoom
        if not b.built:
            # Dim the footprint and show a construction progress bar + label.
            arcade.draw_lrbt_rectangle_filled(sx, sx+w, sy, sy+h, (0,0,0,120))
            arcade.draw_text(BUILDING_STATS.get(b.building_type,{}).get("name","?"),
                             sx+w/2, sy+h+2, (255,220,120,200), 8, anchor_x="center",
                             font_name="Courier New")
            pw = w*0.8; ph = 5*self.zoom; px = sx+(w-pw)/2; py = sy+h/2-ph/2
            arcade.draw_lrbt_rectangle_filled(px, px+pw, py, py+ph, (40,35,20))
            arcade.draw_lrbt_rectangle_filled(px, px+pw*b.construction_progress, py, py+ph,
                                              (240,180,60))
            arcade.draw_lrbt_rectangle_outline(px, px+pw, py, py+ph, (120,100,50), 1)
            arcade.draw_text(f"{int(b.construction_progress*100)}%", sx+w/2, py+ph+2,
                             (255,235,150), 9, anchor_x="center", font_name="Courier New")
            if b.entity_id in self.selected_ids:
                arcade.draw_lrbt_rectangle_outline(sx, sx+w, sy, sy+h, (0,255,0), 2)
            return
        arcade.draw_text(BUILDING_STATS.get(b.building_type,{}).get("name","?"),
                         sx+w/2, sy+h+2, (255,255,255,160), 8, anchor_x="center", font_name="Courier New")
        if b.health < b.max_health: self._draw_hp(sx+w/2, sy+h+12, w*0.8, b.health_fraction)
        if b.entity_id in self.selected_ids:
            arcade.draw_lrbt_rectangle_outline(sx, sx+w, sy, sy+h, (0,255,0), 2)
        if b.producing:
            pw = w*0.7; ph = 4*self.zoom; px = sx+(w-pw)/2; py = sy-8*self.zoom
            arcade.draw_lrbt_rectangle_filled(px, px+pw, py, py+ph, (40,40,40))
            arcade.draw_lrbt_rectangle_filled(px, px+pw*b.production_progress, py, py+ph, (0,200,255))

    def _draw_unit_overlay(self, u):
        sx,sy = self._w2s(u.x, u.y); sz = u.size*self.zoom
        if u.entity_id in self.selected_ids or u.health < u.max_health:
            self._draw_hp(sx, sy+sz/2+4, sz, u.health_fraction)
        if u.entity_id in self.selected_ids:
            arcade.draw_circle_outline(sx, sy, sz/2+2, (0,255,0), 1.5)
        if isinstance(u, Harvester) and u.spice_carried > 0:
            lw=sz*0.6; lx=sx-lw/2; ly=sy-sz/2-6*self.zoom; lh=3*self.zoom
            arcade.draw_lrbt_rectangle_filled(lx,lx+lw,ly,ly+lh,(60,40,10))
            arcade.draw_lrbt_rectangle_filled(lx,lx+lw*u.load_fraction,ly,ly+lh,(220,160,40))

    def _draw_projectiles(self):
        if not self.simulation: return
        for p in self.simulation.combat.projectiles:
            if not p.alive: continue
            sx,sy = self._w2s(p.x, p.y)
            h = self.game_state.players.get(p.owner_id)
            c = HOUSES.get(h.house if h else "atreides",{"color_light":(255,255,100)})["color_light"]
            arcade.draw_circle_filled(sx, sy, 3*self.zoom, c)
            d = math.hypot(p.target_x-p.x, p.target_y-p.y)
            if d > 1:
                tx=p.x-(p.target_x-p.x)/d*8; ty=p.y-(p.target_y-p.y)/d*8
                arcade.draw_line(sx,sy,*self._w2s(tx,ty),(*c,120),2)

    def _draw_hp(self, cx, cy, width, frac):
        h=3*self.zoom; x=cx-width/2
        arcade.draw_lrbt_rectangle_filled(x,x+width,cy,cy+h,(40,0,0))
        c=(0,200,0) if frac>0.6 else ((200,200,0) if frac>0.3 else (200,0,0))
        arcade.draw_lrbt_rectangle_filled(x,x+width*frac,cy,cy+h,c)

    def _draw_sidebar(self):
        self._sidebar_buttons = []  # rebuilt each frame; _sidebar_click hit-tests this
        w,h = self.window.width, self.window.height; sx = w-SIDEBAR_WIDTH
        arcade.draw_lrbt_rectangle_filled(sx,w,0,h,(30,25,18,230))
        arcade.draw_line(sx,0,sx,h,(80,70,50),2)
        p = self.game_state.players[0]
        self._dct("cr",f"Credits: {int(p.credits)}",sx+10,h-30,(220,200,100),14,bold=True)
        pc=(0,200,0) if p.power_balance>=0 else (255,60,60)
        self._dct("pw",f"Power: {p.power_balance} ({p.power_produced}/{p.power_consumed})",sx+10,h-52,pc,11)
        # Hover info
        if self.hover_info:
            arcade.draw_text(self.hover_info, sx+10, MINIMAP_HEIGHT+30, (180,170,130), 9,
                             font_name="Courier New", multiline=True, width=SIDEBAR_WIDTH-20)
        yo = h-85
        if self.selected_ids:
            ent = self.game_state.entities.get(self.selected_ids[0])
            if ent and isinstance(ent, Building):
                nm = BUILDING_STATS.get(ent.building_type,{}).get("name","?")
                arcade.draw_text(nm,sx+10,yo,(200,180,120),13,font_name="Courier New",bold=True); yo-=20
                arcade.draw_text(f"HP: {ent.health}/{ent.max_health}",sx+10,yo,(180,160,110),11,font_name="Courier New"); yo-=22
                if not ent.built:
                    arcade.draw_text(f"Constructing: {int(ent.construction_progress*100)}%",sx+10,yo,(240,180,60),11,font_name="Courier New"); yo-=16
                    arcade.draw_lrbt_rectangle_filled(sx+10,sx+SIDEBAR_WIDTH-20,yo,yo+8,(40,35,20))
                    arcade.draw_lrbt_rectangle_filled(sx+10,sx+10+(SIDEBAR_WIDTH-30)*ent.construction_progress,yo,yo+8,(240,180,60)); yo-=16
                if ent.producing:
                    arcade.draw_text(f"Producing: {ent.producing} ({int(ent.production_progress*100)}%)",sx+10,yo,(0,180,255),11,font_name="Courier New"); yo-=16
                    arcade.draw_lrbt_rectangle_filled(sx+10,sx+SIDEBAR_WIDTH-20,yo,yo+8,(40,40,40))
                    arcade.draw_lrbt_rectangle_filled(sx+10,sx+10+(SIDEBAR_WIDTH-30)*ent.production_progress,yo,yo+8,(0,200,255)); yo-=14
                if ent.production_queue:
                    arcade.draw_text(f"Queue[{len(ent.production_queue)}]: {', '.join(ent.production_queue[:3])}",sx+10,yo,(160,150,110),10,font_name="Courier New"); yo-=18
                if ent.owner_id==0 and ent.can_produce:
                    yo-=5; arcade.draw_text("PRODUCE:",sx+10,yo,(180,160,100),11,font_name="Courier New",bold=True); yo-=5
                    for item in ent.get_producible():
                        yo-=28; self._btn(sx+10,yo,item,ent.entity_id)
            elif ent and isinstance(ent, Unit):
                nm=UNIT_STATS.get(ent.unit_type,{}).get("name","?")
                arcade.draw_text(nm,sx+10,yo,(200,180,120),13,font_name="Courier New",bold=True); yo-=20
                arcade.draw_text(f"HP: {ent.health}/{ent.max_health}",sx+10,yo,(180,160,110),11,font_name="Courier New"); yo-=20
                arcade.draw_text(f"State: {ent.state.value}",sx+10,yo,(150,140,100),11,font_name="Courier New")
                if isinstance(ent,Harvester): yo-=20; arcade.draw_text(f"Spice: {int(ent.spice_carried)}/{int(ent.capacity)}",sx+10,yo,(220,160,40),11,font_name="Courier New")
            if len(self.selected_ids)>1: arcade.draw_text(f"({len(self.selected_ids)} selected)",sx+10,yo-25,(140,130,100),11,font_name="Courier New")
        else:
            self._draw_sidebar_build_menu(sx, yo)

    def _draw_sidebar_build_menu(self, sx, yo):
        # Data-driven: list every player building that can produce something,
        # one section per building type, showing each item it can make. New
        # buildings (e.g. Heavy Factory) appear automatically with no UI edits.
        blds = [e for e in self.game_state.entities.values()
                if isinstance(e, Building) and e.alive and e.owner_id == 0 and e.can_produce]
        blds.sort(key=lambda b: (b.building_type != "construction_yard", b.building_type, b.entity_id))
        seen = set()
        for b in blds:
            if b.building_type in seen:
                continue
            seen.add(b.building_type)
            name = BUILDING_STATS.get(b.building_type, {}).get("name", b.building_type)
            makes_buildings = any(i in BUILDING_STATS for i in b.get_producible())
            label = "BUILDINGS" if makes_buildings else "UNITS"
            yo -= 20
            arcade.draw_text(f"{label} ({name}):", sx+10, yo, (200,180,120), 12,
                             font_name="Courier New", bold=True)
            if b.producing:
                yo -= 16
                arcade.draw_text(f"  {b.producing} ({int(b.production_progress*100)}%)",
                                 sx+10, yo, (0,180,255), 10, font_name="Courier New")
            if b.production_queue:
                yo -= 14
                arcade.draw_text(f"  Queue: {len(b.production_queue)}", sx+10, yo,
                                 (160,150,110), 9, font_name="Courier New")
            for item in b.get_producible():
                yo -= 30
                self._btn(sx+10, yo, item, b.entity_id)

    def _btn(self, x, y, item, building_id):
        """Draw a build button AND register its clickable rect so the draw layout
        and the click hit-test can never drift out of sync."""
        is_building = item in BUILDING_STATS
        self._draw_btn(x, y, item, is_building=is_building)
        self._sidebar_buttons.append({
            "x": x, "y": y, "w": SIDEBAR_WIDTH-30, "h": 24,
            "kind": "place" if is_building else "unit",
            "item": item, "bid": building_id})

    def _fpb(self, btype, pid):
        for eid in self.game_state.players[pid].entity_ids:
            e=self.game_state.entities.get(eid)
            if e and isinstance(e,Building) and e.building_type==btype and e.alive: return e
        return None

    def _draw_btn(self, x, y, item, is_building=False):
        bw,bh=SIDEBAR_WIDTH-30,24
        stats=BUILDING_STATS.get(item) or UNIT_STATS.get(item,{})
        cost=stats.get("cost",0); ok=self.game_state.players[0].credits>=cost
        active=is_building and self.placing_building==item
        bg=(80,70,40) if active else ((60,50,35) if ok else (40,35,28))
        bd=(220,200,80) if active else ((160,140,80) if ok else (80,70,50))
        tc=(255,230,120) if active else ((220,200,130) if ok else (100,90,70))
        arcade.draw_lrbt_rectangle_filled(x,x+bw,y,y+bh,bg)
        arcade.draw_lrbt_rectangle_outline(x,x+bw,y,y+bh,bd,1)
        arcade.draw_text(f"{stats.get('name',item)} ({cost})",x+5,y+4,tc,10,font_name="Courier New")

    def _draw_hud(self):
        w,h=self.window.width,self.window.height
        arcade.draw_lrbt_rectangle_filled(0,w-SIDEBAR_WIDTH,h-28,h,(20,18,12,220))
        p=self.game_state.players[0]
        self._dct("hud",f"{HOUSES[p.house]['name']} | Credits:{int(p.credits)} | Tick:{self.game_state.tick} | U:{len(self.game_state.get_player_units(0))} B:{len(self.game_state.get_player_buildings(0))}",10,h-22,(200,180,120),12)

    def _draw_minimap(self):
        w=self.window.width; mmw,mmh=MINIMAP_WIDTH,MINIMAP_HEIGHT; mx,my=w-SIDEBAR_WIDTH+10,10
        arcade.draw_lrbt_rectangle_filled(mx-2,mx+mmw+2,my-2,my+mmh+2,(50,45,35))
        arcade.draw_lrbt_rectangle_outline(mx-2,mx+mmw+2,my-2,my+mmh+2,(100,90,70),2)
        sxr,syr=mmw/MAP_WIDTH,mmh/MAP_HEIGHT
        for ty in range(0,MAP_HEIGHT,2):
            for tx in range(0,MAP_WIDTH,2):
                c=TERRAIN_COLORS.get(self.game_map.tiles[ty][tx].terrain,(200,180,120))
                arcade.draw_lrbt_rectangle_filled(mx+tx*sxr,mx+(tx+2)*sxr,my+mmh-(ty+2)*syr,my+mmh-ty*syr,c)
        for e in self.game_state.entities.values():
            if isinstance(e,Building) and e.alive:
                c=HOUSES[self.game_state.players[e.owner_id].house]["color_light"]
                arcade.draw_lrbt_rectangle_filled(mx+e.tile_x*sxr,mx+(e.tile_x+e.size_w)*sxr,my+mmh-(e.tile_y+e.size_h)*syr,my+mmh-e.tile_y*syr,c)
        for e in self.game_state.entities.values():
            if isinstance(e,Unit) and e.alive:
                c=HOUSES[self.game_state.players[e.owner_id].house]["color_light"]
                arcade.draw_point(mx+e.tile_x*sxr,my+mmh-(e.tile_y+1)*syr,c,3)
        vw=(self.window.width-SIDEBAR_WIDTH)/(TILE_SIZE*self.zoom); vh=self.window.height/(TILE_SIZE*self.zoom)
        cty=MAP_HEIGHT-(self.cam_y+self.window.height/self.zoom)/TILE_SIZE
        arcade.draw_lrbt_rectangle_outline(mx+self.cam_x/TILE_SIZE*sxr,mx+(self.cam_x/TILE_SIZE+vw)*sxr,my+mmh-(cty+vh)*syr,my+mmh-cty*syr,(255,255,255,150),1)

    def _draw_selection_box(self):
        x1,y1=self.drag_start; x2,y2=self.mouse_x,self.mouse_y
        l,r=min(x1,x2),max(x1,x2); b,t=min(y1,y2),max(y1,y2)
        arcade.draw_lrbt_rectangle_filled(l,r,b,t,(0,255,0,30))
        arcade.draw_lrbt_rectangle_outline(l,r,b,t,(0,255,0,150),1)

    def _draw_building_ghost(self):
        stats=BUILDING_STATS.get(self.placing_building,{}); sz=stats.get("size_tiles",[2,2])
        wx,wy=self._s2w(self.mouse_x,self.mouse_y); tx,ty=world_to_tile(wx,wy)
        ok=self.game_map.can_place_building(tx,ty,sz[0],sz[1])
        c=(0,200,0,80) if ok else (200,0,0,80); bc=(0,255,0,180) if ok else (255,0,0,180)
        # Footprint bottom (matches Building.world_bottom and the placed sprite).
        gsx,gsy=self._w2s(tx*TILE_SIZE,(MAP_HEIGHT-ty-sz[1])*TILE_SIZE)
        gw,gh=sz[0]*TILE_SIZE*self.zoom,sz[1]*TILE_SIZE*self.zoom
        arcade.draw_lrbt_rectangle_filled(gsx,gsx+gw,gsy,gsy+gh,c)
        arcade.draw_lrbt_rectangle_outline(gsx,gsx+gw,gsy,gsy+gh,bc,2)

    def _draw_help(self):
        w,h=self.window.width,self.window.height
        arcade.draw_lrbt_rectangle_filled(0,w,0,h,(0,0,0,180))
        bw2,bh2=520,520; bx=(w-SIDEBAR_WIDTH)/2-bw2/2; by=h/2-bh2/2
        arcade.draw_lrbt_rectangle_filled(bx,bx+bw2,by,by+bh2,(30,25,18,240))
        arcade.draw_lrbt_rectangle_outline(bx,bx+bw2,by,by+bh2,(180,150,80),2)
        arcade.draw_text("CONTROLS",int((w-SIDEBAR_WIDTH)/2),by+bh2-35,(220,190,100),18,anchor_x="center",font_name="Courier New",bold=True)
        for i,l in enumerate(["Z/Q/S/D or Arrows: Scroll camera","Mouse wheel: Zoom",
            "Left click: Select | Drag: Box select","Left click empty: Center camera",
            "Right click: Move/Attack","Shift+Right click: Waypoint queue","X: Stop units | Space: Center base",
            "Ctrl+1-5: Set group | 1-5: Recall","M: Minimap | Enter: Deploy MCV",
            "F5: SAVE | Shift+F5: save slot | F9: LOAD","Escape: Menu","",
            "CY -> Barracks, Refinery, Solar, Light Factory,",
            "      Heavy Factory, Hi-Tech, Airfield, Gun Turret",
            "Barracks -> Soldier, Sniper | Refinery -> Harvester",
            "Light Factory -> Trike, Quad",
            "Heavy Factory -> Harvester, MCV, Tank, Rocket Launcher",
            "Hi-Tech -> Helicopter | Airfield -> Jet Fighter, Bomber",
            "Air units fly over terrain. Buildings show a build bar.","",
            "Press H to close"]):
            arcade.draw_text(l,bx+25,by+bh2-58-i*22,(180,160,120),11,font_name="Courier New")

    def _draw_game_over(self):
        w,h=self.window.width,self.window.height
        arcade.draw_lrbt_rectangle_filled(0,w,0,h,(0,0,0,160))
        wid=self.game_state.winner
        if wid is not None:
            wp=self.game_state.players[wid]; txt=f"{HOUSES[wp.house]['name']} WINS!" if wid==0 else f"{HOUSES[wp.house]['name']} conquered Arrakis!"; c=HOUSES[wp.house]["color_light"]
        else: txt,c="GAME OVER",(200,180,120)
        arcade.draw_text(txt,w/2,h/2+20,c,36,anchor_x="center",font_name="Courier New",bold=True)
        arcade.draw_text("Press ESCAPE for menu",w/2,h/2-30,(160,140,100),14,anchor_x="center",font_name="Courier New")

    def _dct(self, key, text, x, y, color, size=12, bold=False, anchor_x="left"):
        c=self._text_cache.get(key)
        if c is None or c.text!=text or c.x!=x or c.y!=y:
            if c: c.text=text; c.x=x; c.y=y; c.color=color
            else: self._text_cache[key]=arcade.Text(text,x,y,color,size,font_name="Courier New",bold=bold,anchor_x=anchor_x); c=self._text_cache[key]
        else: c.color=color
        c.draw()

    # === INPUT ===
    def on_key_press(self, key, mod):
        self.keys_held.add(key)
        if key==arcade.key.ESCAPE:
            if self.placing_building: self.placing_building=""
            elif self.show_help: self.show_help=False
            else:
                from scenes.menu_scene import MenuScene
                self.window.scene_manager.replace(MenuScene(self.window))
        elif key==arcade.key.H: self.show_help=not self.show_help
        elif key==arcade.key.F5: self._do_save(as_slot=bool(mod & arcade.key.MOD_SHIFT))
        elif key==arcade.key.F9: self._do_load()
        elif key==arcade.key.X:
            uids=[e for e in self.selected_ids if isinstance(self.game_state.entities.get(e),Unit)]
            if uids: self.game_state.queue_command(Command(self.game_state.tick,0,CommandType.STOP,uids))
        elif key==arcade.key.SPACE:
            blds=self.game_state.get_player_buildings(0)
            if blds:
                b=blds[0]; bwx,bwy=tile_to_world(b.tile_x+b.size_w//2,b.tile_y+b.size_h//2)
                self.cam_x=bwx-self.window.width/(2*self.zoom); self.cam_y=bwy-self.window.height/(2*self.zoom); self._clamp_camera()
        elif key==arcade.key.M: self.show_minimap=not self.show_minimap
        elif key in (arcade.key.ENTER,arcade.key.RETURN):
            for eid in self.selected_ids:
                if isinstance(self.game_state.entities.get(eid),MCV):
                    self.game_state.queue_command(Command(self.game_state.tick,0,CommandType.DEPLOY_MCV,[eid]))
        elif key in (arcade.key.KEY_1,arcade.key.KEY_2,arcade.key.KEY_3,arcade.key.KEY_4,arcade.key.KEY_5):
            gn=key-arcade.key.KEY_1
            if mod&(arcade.key.MOD_CTRL|arcade.key.MOD_COMMAND): self.control_groups[gn]=list(self.selected_ids)
            else:
                grp=[e for e in self.control_groups.get(gn,[]) if e in self.game_state.entities and self.game_state.entities[e].alive]
                if grp: self._set_sel(grp)

    def on_key_release(self, key, mod): self.keys_held.discard(key)
    def on_mouse_motion(self, x, y, dx, dy): self.mouse_x=x; self.mouse_y=y

    def on_mouse_press(self, x, y, button, mod):
        if x>self.window.width-SIDEBAR_WIDTH: self._sidebar_click(x,y,button); return
        if self.show_minimap and self._mm_hit(x,y): self._mm_click(x,y); return
        if button==arcade.MOUSE_BUTTON_LEFT:
            if self.placing_building:
                wx,wy=self._s2w(x,y); tx,ty=world_to_tile(wx,wy)
                sz=BUILDING_STATS.get(self.placing_building,{}).get("size_tiles",[2,2])
                if self.game_map.can_place_building(tx,ty,sz[0],sz[1]):
                    self.game_state.queue_command(Command(self.game_state.tick,0,CommandType.PLACE_BUILDING,target_x=tx,target_y=ty,params={"building_type":self.placing_building}))
                self.placing_building=""
            else: self.drag_start=(x,y); self.dragging=False
        elif button==arcade.MOUSE_BUTTON_RIGHT:
            if self.placing_building: self.placing_building=""; return
            wx,wy=self._s2w(x,y); tx,ty=world_to_tile(wx,wy)
            tgt=self._entity_at(wx,wy,True)
            uids=[e for e in self.selected_ids if isinstance(self.game_state.entities.get(e),Unit) and self.game_state.entities[e].owner_id==0]
            is_wp=bool(mod&arcade.key.MOD_SHIFT)
            if tgt and uids: self.game_state.queue_command(Command(self.game_state.tick,0,CommandType.ATTACK,uids,target_entity_id=tgt.entity_id))
            elif uids: self.game_state.queue_command(Command(self.game_state.tick,0,CommandType.MOVE,uids,target_x=tx,target_y=ty,params={"waypoint":is_wp}))

    def on_mouse_release(self, x, y, button, mod):
        if button==arcade.MOUSE_BUTTON_LEFT and self.drag_start:
            if self.dragging:
                self._box_sel(*self.drag_start, x, y)
            else:
                wx,wy=self._s2w(x,y)
                e=self._entity_at(wx,wy)
                if e and e.owner_id==0:
                    self._set_sel([e.entity_id])
                else:
                    self._set_sel([])
                    # CENTER CAMERA on clicked point
                    self.cam_x=wx-(self.window.width-SIDEBAR_WIDTH)/(2*self.zoom)
                    self.cam_y=wy-self.window.height/(2*self.zoom)
                    self._clamp_camera()
            self.drag_start=None; self.dragging=False

    def on_mouse_drag(self, x, y, dx, dy, buttons, mod):
        self.mouse_x=x; self.mouse_y=y
        if buttons&arcade.MOUSE_BUTTON_LEFT and self.drag_start:
            if abs(x-self.drag_start[0])+abs(y-self.drag_start[1])>5: self.dragging=True

    def on_mouse_scroll(self, x, y, sx, sy):
        oz=self.zoom
        if sy>0: self.zoom=min(ZOOM_MAX,self.zoom+ZOOM_STEP)
        elif sy<0: self.zoom=max(ZOOM_MIN,self.zoom-ZOOM_STEP)
        if oz!=self.zoom:
            wx=x/oz+self.cam_x; wy=y/oz+self.cam_y
            self.cam_x=wx-x/self.zoom; self.cam_y=wy-y/self.zoom; self._clamp_camera()

    def _set_sel(self, ids):
        for e in self.selected_ids:
            ent=self.game_state.entities.get(e)
            if ent: ent.selected=False
        self.selected_ids=ids
        for e in ids:
            ent=self.game_state.entities.get(e)
            if ent: ent.selected=True

    def _box_sel(self, x1, y1, x2, y2):
        l,r=min(x1,x2),max(x1,x2); b,t=min(y1,y2),max(y1,y2)
        ids=[e.entity_id for e in self.game_state.entities.values()
             if isinstance(e,Unit) and e.alive and e.owner_id==0
             and l<=self._w2s(e.x,e.y)[0]<=r and b<=self._w2s(e.x,e.y)[1]<=t]
        self._set_sel(ids)

    def _entity_at(self, wx, wy, enemy_only=False):
        best,bd=None,float('inf')
        for e in self.game_state.entities.values():
            if not e.alive: continue
            if enemy_only and e.owner_id==0: continue
            if isinstance(e,Building):
                bwx=e.world_left; bwy=e.world_bottom
                if bwx<=wx<=bwx+e.size_w*TILE_SIZE and bwy<=wy<=bwy+e.size_h*TILE_SIZE: return e
            elif isinstance(e,Unit):
                d=math.hypot(e.x-wx,e.y-wy)
                if d<e.size*1.5 and d<bd: best,bd=e,d
        return best

    def _mm_hit(self, x, y):
        mx=self.window.width-SIDEBAR_WIDTH+10
        return mx<=x<=mx+MINIMAP_WIDTH and 10<=y<=10+MINIMAP_HEIGHT

    def _mm_click(self, x, y):
        mx=self.window.width-SIDEBAR_WIDTH+10
        self.cam_x=(x-mx)/MINIMAP_WIDTH*MAP_PIXEL_WIDTH-(self.window.width-SIDEBAR_WIDTH)/(2*self.zoom)
        self.cam_y=(y-10)/MINIMAP_HEIGHT*MAP_PIXEL_HEIGHT-self.window.height/(2*self.zoom)
        self._clamp_camera()

    def _sidebar_click(self, x, y, button):
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        # Hit-test the buttons registered by the last _draw_sidebar pass. Because
        # draw and click share the exact same rects, every producible item is
        # clickable and the two can never fall out of alignment.
        for b in self._sidebar_buttons:
            if b["x"] <= x <= b["x"]+b["w"] and b["y"] <= y <= b["y"]+b["h"]:
                if b["kind"] == "place":
                    self.placing_building = b["item"]
                else:
                    self.game_state.queue_command(Command(
                        self.game_state.tick, 0, CommandType.BUILD_UNIT,
                        [b["bid"]], params={"unit_type": b["item"]}))
                return

    def on_resize(self, w, h):
        # A fresh Camera2D adopts the new window size for its viewport; the
        # position/zoom we set each frame keeps world<->screen alignment.
        if self.world_cam is not None:
            self.world_cam = arcade.Camera2D()
        self._clamp_camera()
