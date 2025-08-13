import os
import json
from typing import Dict, Tuple, Optional, Callable
import pygame

Color = Tuple[int, int, int]

# ---------- Palette (cold war aesthetic) ----------
OCEAN = (8, 20, 28)
USA_DARK_BLUE = (18, 45, 110)
USSR_DARK_RED = (120, 20, 25)
NATO_LIGHT = (92, 140, 190)
WARSAW_LIGHT = (182, 86, 86)
NONALIGNED_TAN = (132, 124, 96)
OUT_OF_PLAY_GRAY = (140, 142, 146)
BORDER_RGBA = (0, 0, 0, 255)  # solid black borders
TOOLTIP_BG: Color = (24, 30, 36)       # charcoal panel
TOOLTIP_BORDER: Color = (180, 186, 192) # desaturated light border
TOOLTIP_TEXT: Color = (234, 238, 242)   # off‑white text


# ---------------------------- file helpers ----------------------------
def _read_mapping(path: str) -> Dict[Color, str]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    mapping: Dict[Color, str] = {}
    for k, v in raw.items():
        if isinstance(k, str):
            parts = tuple(int(x) for x in k.split(","))
        else:
            parts = tuple(k)
        mapping[parts] = v
    return mapping


def _assets_path(*parts: str) -> str:
    base = os.path.join(os.path.dirname(__file__), "assets")
    return os.path.join(base, *parts)


# ---------------------------- Map Manager ----------------------------
class MapManager:
    """Render an ID-color world map and answer country clicks.

    Required assets in ./assets:
      - world_idmap.png        (flat ID colors, no antialiasing)
      - id_to_country.json     ("R,G,B" -> country name)
    """

    def __init__(
        self,
        surface: pygame.Surface,
        countries: Dict[str, object],
        tooltip_font: pygame.font.Font,
        idmap_path: Optional[str] = None,
        mapping_path: Optional[str] = None,
        on_click: Optional[Callable[[Optional[object]], None]] = None,
    ) -> None:
        self.surface = surface
        self.on_click = on_click
        self.tooltip_font = tooltip_font

        idmap_path = idmap_path or _assets_path("world_idmap.png")
        mapping_path = mapping_path or _assets_path("id_to_country.json")

        # Load ID map (must be flat-colored, already cleaned in QGIS)
        self.id_surface = pygame.image.load(idmap_path).convert()
        self.map_w, self.map_h = self.id_surface.get_size()
        self.color_to_name = _read_mapping(mapping_path)

        # countries dict from setup.py contains ONLY playable countries → ground truth
        self.countries_by_name = countries
        self.playable_names = set(countries.keys())

        # Prebuild color surfaces (source resolution)
        self.colored = pygame.Surface((self.map_w, self.map_h)).convert()
        self.borders = pygame.Surface((self.map_w, self.map_h), pygame.SRCALPHA)

        # Cache for scaling
        self._scaled_colored: Optional[pygame.Surface] = None
        self._scaled_borders: Optional[pygame.Surface] = None
        self._dest_rect = self._fit_to_surface(self.surface.get_rect())
        self._cache_size = None

        # Build initial layers
        self._paint_map_with_gray_nonplayables()
        self._build_borders_playables_only(thickness=2)

    # ---------------------------- paint helpers ----------------------------
    def _fit_to_surface(self, rect: pygame.Rect) -> pygame.Rect:
        ar = self.map_w / self.map_h
        w = rect.w
        h = int(w / ar)
        if h > rect.h:
            h = rect.h
            w = int(h * ar)
        r = pygame.Rect(0, 0, w, h)
        r.center = rect.center
        return r

    def _bloc_palette(self, name: str) -> Color:
        # name is guaranteed playable when this is called
        cobj = self.countries_by_name.get(name)
        bloc = getattr(cobj, "bloc", None)
        bloc_name = bloc if isinstance(bloc, str) else (getattr(bloc, "name", None) or "")
        if name == "USA":
            return USA_DARK_BLUE
        if name == "USSR":
            return USSR_DARK_RED
        if bloc_name == "NATO":
            return NATO_LIGHT
        if bloc_name == "Warsaw Pact":
            return WARSAW_LIGHT
        return NONALIGNED_TAN

    def _paint_map_with_gray_nonplayables(self) -> None:
        """Paint:
        - Ocean → OCEAN
        - All *non-playable* land (even if missing from JSON) → OUT_OF_PLAY_GRAY
        - Playables → bloc colors
        This fixes the case where unmapped IDs were falling through to ocean.
        """
        try:
            import numpy as np
            id_arr = pygame.surfarray.pixels3d(self.id_surface).copy()
            keys = ((id_arr[:, :, 0].astype(np.uint32) << 16) |
                    (id_arr[:, :, 1].astype(np.uint32) << 8) |
                     id_arr[:, :, 2].astype(np.uint32))

            # Ocean mask from JSON, else infer by mode
            ocean_ids = []
            for (r, g, b), name in self.color_to_name.items():
                if name == "__OCEAN__":
                    ocean_ids.append((r << 16) | (g << 8) | b)
            if ocean_ids:
                ocean_mask = np.isin(keys, np.array(ocean_ids, dtype=np.uint32))
            else:
                vals, counts = np.unique(keys, return_counts=True)
                ocean_mask = (keys == vals[counts.argmax()])

            # Playable IDs from setup countries
            playable_ids = []
            for (r, g, b), name in self.color_to_name.items():
                if name and name != "__OCEAN__" and name in self.playable_names:
                    playable_ids.append((r << 16) | (g << 8) | b)
            playable_mask = np.isin(keys, np.array(playable_ids, dtype=np.uint32)) if playable_ids else np.zeros_like(keys, dtype=bool)

            land_mask = ~ocean_mask
            nonplayable_mask = land_mask & (~playable_mask)  # <-- anything not ocean and not playable

            out = np.empty_like(id_arr)
            out[:, :, :] = np.array(OCEAN, dtype=np.uint8)
            # paint non-playable land gray first
            out[nonplayable_mask] = OUT_OF_PLAY_GRAY

            # paint playables by bloc color
            # build LUT from playable id->name for palette lookup
            id_to_name = {}
            for (r, g, b), name in self.color_to_name.items():
                if name and name != "__OCEAN__" and name in self.playable_names:
                    id_to_name[(r << 16) | (g << 8) | b] = name
            if id_to_name:
                for key, nm in id_to_name.items():
                    mask = (keys == key)
                    out[mask] = self._bloc_palette(nm)

            pygame.surfarray.blit_array(self.colored, out)
        except Exception:
            # Slow fallback: treat any non-ocean color that isn't a playable as gray
            self.colored.lock()
            px = pygame.PixelArray(self.colored)
            fmt = self.colored.map_rgb
            # Build ocean set and playable set for quick checks
            ocean_set = {rgb for rgb, nm in self.color_to_name.items() if nm == "__OCEAN__"}
            playable_set = {rgb for rgb, nm in self.color_to_name.items() if nm and nm != "__OCEAN__" and nm in self.playable_names}
            for y in range(self.map_h):
                for x in range(self.map_w):
                    rgb = self.id_surface.get_at((x, y))[:3]
                    name = self.color_to_name.get(rgb)
                    if (rgb in ocean_set) or (name == "__OCEAN__"):
                        color = OCEAN
                    elif (rgb in playable_set) or (name in self.playable_names if name else False):
                        nm = name
                        if not nm:  # unlikely here
                            color = NONALIGNED_TAN
                        else:
                            color = self._bloc_palette(nm)
                    else:
                        color = OUT_OF_PLAY_GRAY
                    px[x, y] = fmt(color)
            del px
            self.colored.unlock()
        self._cache_size = None

    def _build_borders_playables_only(self, thickness: int = 2) -> None:
        """Create a black border wherever a *playable* country touches anything
        different (ocean, non-playable, or another playable). Non-playables get
        no borders.
        """
        self.borders.fill((0, 0, 0, 0))
        try:
            import numpy as np
            id_arr = pygame.surfarray.pixels3d(self.id_surface).copy()
            keys = ((id_arr[:, :, 0].astype(np.uint32) << 16) |
                    (id_arr[:, :, 1].astype(np.uint32) << 8) |
                     id_arr[:, :, 2].astype(np.uint32))

            # Build playable mask from setup-provided country names
            playable_ids = []
            for (r, g, b), name in self.color_to_name.items():
                if name and name != "__OCEAN__" and name in self.playable_names:
                    playable_ids.append((r << 16) | (g << 8) | b)
            playable_mask = np.isin(keys, np.array(playable_ids, dtype=np.uint32)) if playable_ids else np.zeros_like(keys, dtype=bool)

            base = keys
            edge = np.zeros_like(base, dtype=bool)

            def shift(a, dx, dy):
                b = a.copy()
                if dx == -1:
                    b[:, :-1] = a[:, 1:]
                elif dx == 1:
                    b[:, 1:] = a[:, :-1]
                if dy == -1:
                    b[:-1, :] = a[1:, :]
                elif dy == 1:
                    b[1:, :] = a[:-1, :]
                return b

            # draw borders only where at least one side is playable
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                neigh = shift(base, dx, dy)
                diff = (base != neigh)
                neigh_playable = shift(playable_mask, dx, dy)
                edge |= diff & (playable_mask | neigh_playable)

            # Dilate to requested thickness (outward only is fine here)
            mask = edge
            for _ in range(max(0, thickness-1)):
                dil = mask.copy()
                dil[1:, :] |= mask[:-1, :]
                dil[:-1, :] |= mask[1:, :]
                dil[:, 1:] |= mask[:, :-1]
                dil[:, :-1] |= mask[:, 1:]
                # diagonals
                d = dil.copy()
                d[1:, 1:] |= mask[:-1, :-1]
                d[1:, :-1] |= mask[:-1, 1:]
                d[:-1, 1:] |= mask[1:, :-1]
                d[:-1, :-1] |= mask[1:, 1:]
                mask = d

            arr = pygame.surfarray.pixels3d(self.borders)
            alpha = pygame.surfarray.pixels_alpha(self.borders)
            arr[mask] = (0, 0, 0)
            alpha[mask] = 255
        except Exception:
            # Slow fallback: only outline pixels that belong to playables
            playables = set()
            for rgb, name in self.color_to_name.items():
                if name and name != "__OCEAN__" and name in self.playable_names:
                    playables.add(rgb)
            self.borders.lock()
            for y in range(self.map_h):
                for x in range(self.map_w):
                    a = self.id_surface.get_at((x, y))[:3]
                    if a not in playables:
                        continue
                    for nx, ny in ((x+1,y),(x,y+1),(x-1,y),(x,y-1)):
                        if 0 <= nx < self.map_w and 0 <= ny < self.map_h:
                            if self.id_surface.get_at((nx, ny))[:3] != a:
                                self.borders.set_at((x, y), (0,0,0,255))
                                break
            self.borders.unlock()
        self._cache_size = None
    
    def country_name_at_point(self, pos: Tuple[int, int]) -> Optional[str]:
        """Return the *name string* at screen-space pos (None for ocean/out of bounds).
        Unlike country_at_point, this shows **any mapped country name**, even if non-playable,
        which is better for students exploring the map.
        """
        if not hasattr(self, "_dest_rect") or not self._dest_rect.collidepoint(pos):
            return None
        sx = (pos[0] - self._dest_rect.left) / self._dest_rect.w
        sy = (pos[1] - self._dest_rect.top) / self._dest_rect.h
        x = min(self.map_w - 1, max(0, int(sx * self.map_w)))
        y = min(self.map_h - 1, max(0, int(sy * self.map_h)))
        rgb = self.id_surface.get_at((x, y))[:3]
        name = self.color_to_name.get(rgb)
        if not name or name == "__OCEAN__":
            return None
        return name
    

    def draw_hover_tooltip(self, surface: pygame.Surface, mouse_pos: Tuple[int, int], font: Optional[pygame.font.Font] = None) -> None:
        """Render a Cold War–style tooltip just up-right of the cursor with the country name.
    
        - Hides on ocean/out of bounds.
        - Stays on-screen (repositions left/up if near edges).
        - Independent of your draw() scaling; uses country_name_at_point() for hit test.
    
        Parameters
        ----------
        surface : pygame.Surface
            The primary screen to draw onto (same you pass to MapManager).
        mouse_pos : (x, y)
            Current mouse coordinates in screen space.
        font : pygame.font.Font or None
            Optional font. If None, a legible default will be created.
        """
        name = self.country_name_at_point(mouse_pos)
        if not name:
            return
    
        # Prepare font
        if font is None:
            font = pygame.font.SysFont("consolas,menlo,dejavusansmono,monospace", 18, bold=False)
    
        text_surf = font.render(name, True, TOOLTIP_TEXT)
        tw, th = text_surf.get_size()
        pad_x, pad_y = 10, 8
        box_w, box_h = tw + pad_x * 2, th + pad_y * 2 + 3  # +3 for accent line
    
        # Desired position: a little up-right of the cursor
        mx, my = mouse_pos
        ox, oy = 14, -18
        x = mx + ox
        y = my + oy - box_h
    
        # Keep fully on-screen
        sw, sh = surface.get_size()
        if x + box_w > sw - 6:
            x = sw - box_w - 6
        if x < 6:
            x = 6
        if y < 6:
            y = my + 18  # place below the cursor if not enough space above
            if y + box_h > sh - 6:
                y = sh - box_h - 6
    
        # Panel
        panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        panel.fill((0,0,0,0))
        # background
        pygame.draw.rect(panel, TOOLTIP_BG, panel.get_rect(), border_radius=6)
        # border
        pygame.draw.rect(panel, TOOLTIP_BORDER, panel.get_rect(), width=1, border_radius=6)
        # accent line at the top
        pygame.draw.line(panel, self._bloc_palette(name), (6, 5), (box_w - 6, 5), 2)
    
        # text
        panel.blit(text_surf, (pad_x, pad_y + 4))
    
        # subtle drop shadow
        shadow = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0,0,0,90), shadow.get_rect(), border_radius=6)
        surface.blit(shadow, (x+2, y+2))
        surface.blit(panel, (x, y))

    # ---------------------------- public API ----------------------------
    def draw(self) -> None:
        if self._cache_size != self.surface.get_size():
            self._dest_rect = self._fit_to_surface(self.surface.get_rect())
            self._scaled_colored = pygame.transform.scale(self.colored, self._dest_rect.size)
            self._scaled_borders = pygame.transform.scale(self.borders, self._dest_rect.size)
            self._cache_size = self.surface.get_size()
        self.surface.fill(OCEAN)
        self.surface.blit(self._scaled_colored, self._dest_rect)
        self.surface.blit(self._scaled_borders, self._dest_rect)
        mouse_pos = pygame.mouse.get_pos()
        self.draw_hover_tooltip(self.surface, mouse_pos, self.tooltip_font)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.VIDEORESIZE:
            self._cache_size = None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            c = self.country_at_point(event.pos)
            if self.on_click:
                self.on_click(c)

    def country_at_point(self, pos) -> Optional[object]:
        if not self._dest_rect.collidepoint(pos):
            return None
        sx = (pos[0] - self._dest_rect.left) / self._dest_rect.w
        sy = (pos[1] - self._dest_rect.top) / self._dest_rect.h
        x = min(self.map_w - 1, max(0, int(sx * self.map_w)))
        y = min(self.map_h - 1, max(0, int(sy * self.map_h)))
        rgb = self.id_surface.get_at((x, y))[:3]
        name = self.color_to_name.get(rgb)
        if not name or name == "__OCEAN__":
            return None
        return self.countries_by_name.get(name)

    def recolor_after_bloc_change(self) -> None:
        self._paint_map_with_gray_nonplayables()
        # borders remain valid (based on ID boundaries)


# ---------------------------- Demo ----------------------------
if __name__ == "__main__":
    import setup

    def _run_demo() -> None:
        pygame.init()
        tooltip_font = pygame.font.SysFont("consolas,menlo,dejavusansmono,monospace", 18)
        screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        pygame.display.set_caption("MapManager Demo — click a country")
        blocs, countries = setup.init_countries_and_blocs()

        font = pygame.font.SysFont(None, 24)
        selected_text: Optional[str] = None
        


        def on_click(c):
            nonlocal selected_text
            if c is None:
                selected_text = "None"
            else:
                # Example: cycle bloc on click to prove recolor works
                old = c.bloc if isinstance(c.bloc, str) else getattr(c.bloc, "name", c.bloc)
                if old == "NATO":
                    c.bloc = "Warsaw Pact"
                elif old == "Warsaw Pact":
                    c.bloc = "Non-Aligned"
                else:
                    c.bloc = "NATO"
                selected_text = f"{getattr(c, 'name', str(c))} → {c.bloc}"
                manager.recolor_after_bloc_change()


        manager = MapManager(screen, countries, tooltip_font, on_click=on_click)

        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                manager.handle_event(event)

            manager.draw()
            
            if selected_text:
                txt = font.render(selected_text, True, (230, 230, 230))
                screen.blit(txt, (20, 20))
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()

    _run_demo()
