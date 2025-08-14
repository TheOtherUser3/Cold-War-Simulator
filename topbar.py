import pygame
from typing import Optional, Tuple, Callable

from gamestate import GameState  # DEFCON + turn owner
from models import Country  # typing clarity only
from setup import init_countries_and_blocs

# ---------- Cold War palette ----------
BG = (18, 22, 30)
PANEL = (27, 34, 46)
ACCENT = (120, 175, 255)
GREEN = (60, 180, 90)
YELLOW = (210, 175, 60)
ORANGE = (220, 120, 60)
RED = (200, 60, 60)
CYAN = (80, 190, 200)
# Bloc accent colors for badge
BLOC_COLORS = {
    "NATO": (98, 128, 180),
    "Warsaw Pact": (180, 96, 96),
    "Non-Aligned": (180, 160, 120),
}


class TopBarManager:
    """
    Cold War–style HUD for game-wide metrics.

    Displays the *currently playing* country's stats + global DEFCON from GameState.

    Public API:
      - handle_event(event)
      - on_resize(size)
      - draw()

    Optional callbacks you can pass in:
      - on_click_arms(country: Optional[str])
      - on_click_space(country: Optional[str])
    """

    HEIGHT = 64

    def __init__(
        self,
        surface: pygame.Surface,
        game: GameState,
        *,
        on_click_arms: Optional[Callable[[Optional[str]], None]] = None,
        on_click_space: Optional[Callable[[Optional[str]], None]] = None,
    ) -> None:
        self.surface = surface
        self.game = game
        self.on_click_arms = on_click_arms
        self.on_click_space = on_click_space

        # live values (mirrored from GameState each frame)
        self.pp = 0
        self.war_power = 0
        self.arms_tier = 0
        self.space_tier = 0
        self.defcon = 5
        self.subject_name: Optional[str] = None
        self._bloc_name: Optional[str] = None
        self._turn_skip: int = 0
        self._arms_lock: int = 0

        # layout cache
        self._bar_rect = pygame.Rect(0, 0, *self.surface.get_size())
        self._bar_rect.height = self.HEIGHT
        self._font_big = pygame.font.SysFont("Segoe UI Semibold", 22)
        self._font_small = pygame.font.SysFont("Segoe UI", 16)
        self._hint_font = pygame.font.SysFont("consolas,menlo,dejavusansmono,monospace", 14)

        # interactive hit boxes
        self._hit_pp = pygame.Rect(0, 0, 0, 0)
        self._hit_war = pygame.Rect(0, 0, 0, 0)
        self._hit_arms = pygame.Rect(0, 0, 0, 0)
        self._hit_space = pygame.Rect(0, 0, 0, 0)
        self._hit_defcon = pygame.Rect(0, 0, 0, 0)

        # tooltip state
        self._hover: Optional[Tuple[str, Tuple[int, int]]] = None

        self._recompute_layout()

    # -------------------------- Game sync --------------------------
    def _sync_from_game(self) -> None:
        """Pull values from the GameState and its currently-playing country.
        Safe against None / missing fields.
        """
        c: Optional[Country] = None

        # Try common getters/attributes for the current country
        getter = getattr(self.game, "get_currently_playing", None)
        if callable(getter):
            c = getter()
        else:
            getter2 = getattr(self.game, "get_current_country", None)
            if callable(getter2):
                c = getter2()
            else:
                c = getattr(self.game, "currently_playing", None) or getattr(self.game, "current_country", None)

        # Fallback to any country from game.countries
        if c is None:
            try:
                c = next(iter(self.game.countries.values()))
            except Exception:
                c = None

        if c is not None:
            self.pp = int(max(0, getattr(c, "pp", 0)))
            self.war_power = int(getattr(c, "war_power", 0))
            self.arms_tier = int(max(0, min(4, getattr(c, "arms_race", 0))))
            self.space_tier = int(max(0, min(4, getattr(c, "space_race", 0))))
            self._turn_skip = int(getattr(c, "turn_skip", 0))
            self.subject_name = getattr(c, "name", None)
            bloc = getattr(c, "bloc", None)
            self._bloc_name = bloc if isinstance(bloc, str) else getattr(bloc, "name", None)
        else:
            self.pp = self.war_power = self.arms_tier = self.space_tier = 0
            self._turn_skip = 0
            self.subject_name = None

        # DEFCON and Arms-lock from GameState
        get_def = getattr(self.game, "get_defcon", None)
        if callable(get_def):
            val = get_def()
        else:
            val = getattr(self.game, "defcon", 5)
        try:
            self.defcon = int(max(1, min(5, val)))
        except Exception:
            self.defcon = 5

        self._arms_lock = int(getattr(self.game, "arms_race_lock", 0))

    # -------------------------- Public API --------------------------
    def on_resize(self, size: Tuple[int, int]) -> None:
        self._bar_rect.size = size
        self._bar_rect.height = self.HEIGHT
        self._recompute_layout()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # disable arms click if locked
            if self._hit_arms.collidepoint(event.pos) and self.on_click_arms and self._arms_lock <= 0:
                self.on_click_arms(self.subject_name)
            elif self._hit_space.collidepoint(event.pos) and self.on_click_space:
                self.on_click_space(self.subject_name)

    def draw(self) -> None:
        self._sync_from_game()
        self._draw_bar_bg()
        x = self._left_start()
        x = self._draw_pp(x)
        x += 36
        x = self._draw_war_power(x)
        x += 36
        arms_end_x = self._draw_race(x, kind="Arms", tier=self.arms_tier, rect_store=self._hit_arms)
        if self._arms_lock > 0:
            self._draw_arms_lock_overlay(self._hit_arms)
        x = arms_end_x + 24
        x = self._draw_race(x, kind="Space", tier=self.space_tier, rect_store=self._hit_space)
        # right side: DEFCON
        self._draw_defcon()
        # skip-turn stamp if needed
        if self._turn_skip > 0:
            self._draw_skip_stamp(self._turn_skip)
        self._draw_tooltip()

    # -------------------------- Layout/Drawing --------------------------
    def _recompute_layout(self) -> None:
        w, _ = self.surface.get_size()
        box_w = 300
        self._defcon_rect = pygame.Rect(w - box_w - 8, 8, box_w, self.HEIGHT - 16)

    def _draw_bar_bg(self) -> None:
        # Background strip with subtle divider + shadow
        bar = pygame.Surface((self._bar_rect.w, self.HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(bar, PANEL, bar.get_rect())
        pygame.draw.line(bar, (255, 255, 255, 25), (0, self.HEIGHT - 1), (self._bar_rect.w, self.HEIGHT - 1))
        shadow = pygame.Surface((self._bar_rect.w, 6), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 110), shadow.get_rect())
        self.surface.blit(bar, (0, 0))
        self.surface.blit(shadow, (0, self.HEIGHT))

        if self.subject_name:
            chip = self._render_chip(self.subject_name, self._bloc_color_for_current())
            cy = (self.HEIGHT - chip.get_height()) // 2
            self.surface.blit(chip, (12, cy))

    def _render_chip(self, text: str, accent: Tuple[int, int, int]) -> pygame.Surface:
        # Cold War badge: pill with left accent bar + small star emblem
        pad_x, pad_y = 12, 6
        ts = self._font_small.render(text, True, (230, 235, 242))
        w, h = ts.get_width() + pad_x * 2 + 18, ts.get_height() + pad_y * 2
        chip = pygame.Surface((w, h), pygame.SRCALPHA)
        rect = chip.get_rect()
        pygame.draw.rect(chip, (36, 44, 60), rect, border_radius=14)
        pygame.draw.rect(chip, (255, 255, 255, 40), rect, 1, border_radius=14)
        # left accent bar
        pygame.draw.rect(chip, accent, pygame.Rect(0, 0, 6, h), border_radius=12)
        # star emblem inside a thin circle
        cx, cy = 12, rect.centery
        pygame.draw.circle(chip, (180, 190, 210), (cx, cy), 8, 1)
        pts = [(cx, cy-6), (cx+2, cy-1), (cx+7, cy-1), (cx+3, cy+2), (cx+4, cy+7), (cx, cy+4), (cx-4, cy+7), (cx-3, cy+2), (cx-7, cy-1), (cx-2, cy-1)]
        pygame.draw.polygon(chip, (200, 210, 230), pts)
        chip.blit(ts, (pad_x + 18, pad_y))
        return chip

    def _draw_label_value(self, x: int, label: str, value_text: str, icon_drawer: Callable[[pygame.Surface, Tuple[int, int]], None]) -> int:
        y = 8
        icon_size = 26
        text_gap = 10
        value_gap = 2
        lbl = self._font_small.render(label, True, (182, 190, 200))
        val = self._font_big.render(value_text, True, (236, 241, 246))
        start_x = x
        icon_s = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
        icon_drawer(icon_s, (icon_size // 2, icon_size // 2))
        self.surface.blit(icon_s, (start_x, y))
        start_x += icon_size + text_gap
        self.surface.blit(lbl, (start_x, y))
        self.surface.blit(val, (start_x, y + lbl.get_height() + value_gap))
        w = max(icon_size + text_gap + max(lbl.get_width(), val.get_width()), 100)
        return x + w

    def _draw_pp(self, x: int) -> int:
        def icon(s: pygame.Surface, c: Tuple[int, int]):
            # Briefcase + star (Cold War admin power)
            r = pygame.Rect(c[0]-10, c[1]-6, 20, 14)
            pygame.draw.rect(s, (190, 200, 215), r, 2, border_radius=3)
            pygame.draw.rect(s, (190, 200, 215), (c[0]-4, c[1]-10, 8, 3), 1, border_radius=1)  # handle
            # small star emblem on case
            pts = [(c[0], c[1]-1), (c[0]+2, c[1]+2), (c[0]+6, c[1]+2), (c[0]+3, c[1]+4), (c[0]+4, c[1]+8), (c[0], c[1]+5), (c[0]-4, c[1]+8), (c[0]-3, c[1]+4), (c[0]-6, c[1]+2), (c[0]-2, c[1]+2)]
            pygame.draw.polygon(s, ACCENT, pts)
        self._hit_pp = pygame.Rect(x, 0, 140, self.HEIGHT)
        return self._draw_label_value(x, "PP", f"{self.pp}", icon)

    def _draw_war_power(self, x: int) -> int:
        def icon(s: pygame.Surface, c: Tuple[int, int]):
            # Radar scope (Cold War surveillance vibe)
            pygame.draw.circle(s, (200, 210, 220), c, 13, 2)
            pygame.draw.circle(s, (120, 130, 150), c, 8, 1)
            pygame.draw.circle(s, (120, 130, 150), c, 4, 1)
            # sweep line
            pygame.draw.line(s, ORANGE, c, (c[0]+10, c[1]-6), 2)
            # blips
            pygame.draw.circle(s, ORANGE, (c[0]-5, c[1]-2), 2)
            pygame.draw.circle(s, ORANGE, (c[0]+3, c[1]+4), 2)
        self._hit_war = pygame.Rect(x, 0, 160, self.HEIGHT)
        return self._draw_label_value(x, "War", f"{self.war_power}", icon)

    def _draw_race(self, x: int, *, kind: str, tier: int, rect_store: pygame.Rect) -> int:
        y = 8
        label = f"{kind}"
        lbl = self._font_small.render(label, True, (182, 190, 200))
        self.surface.blit(lbl, (x, y))
        y += lbl.get_height() + 4
        slot_w, slot_h, gap = 24, 14, 8
        total_w = slot_w * 5 + gap * 4
        rect_store.update(x, 0, total_w, self.HEIGHT)
        for i in range(5):
            r = pygame.Rect(x + i * (slot_w + gap), y, slot_w, slot_h)
            pygame.draw.rect(self.surface, (64, 76, 96), r, border_radius=6)
            pygame.draw.rect(self.surface, (255, 255, 255, 36), r, 1, border_radius=6)
            if i <= tier - 1:
                col = CYAN if kind == "Space" else YELLOW
                pygame.draw.rect(self.surface, col, r.inflate(-4, -4), border_radius=4)
        return x + total_w

    def _draw_arms_lock_overlay(self, rect: pygame.Rect) -> None:
        """Draw a stronger lock: dim, diagonal X, and a center padlock.
        Clicking is disabled elsewhere when _arms_lock > 0.
        """
        # Dim the area
        overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        overlay.fill((10, 10, 12, 150))
        self.surface.blit(overlay, rect.topleft)
    
        # Diagonal X
        pygame.draw.line(self.surface, (200, 200, 210), (rect.left + 2, rect.top + 2), (rect.right - 2, rect.bottom - 2), 2)
        pygame.draw.line(self.surface, (200, 200, 210), (rect.left + 2, rect.bottom - 2), (rect.right - 2, rect.top + 2), 2)
    
        # Center padlock icon
        cx = rect.centerx
        cy = rect.centery
        body_w, body_h = 18, 16
        body = pygame.Rect(cx - body_w // 2, cy - body_h // 2 + 4, body_w, body_h)
        pygame.draw.rect(self.surface, (220, 220, 230), body, 2, border_radius=3)
        # shackle
        pygame.draw.arc(self.surface, (220, 220, 230), (cx - 8, cy - 8, 16, 12), 3.14, 0, 2)
    
        # LOCKED text below
        txt = self._font_small.render("LOCKED", True, (235, 235, 240))
        tx = rect.centerx - txt.get_width() // 2
        ty = rect.bottom + 2  # just above the metric labels line
        self.surface.blit(txt, (tx, max(0, ty - self.HEIGHT + rect.height)))


    def _draw_skip_stamp(self, turns_left: int) -> None:
        """Render a prominent red banner to the RIGHT of the Arms/Space tracks.
        Vertically centered in the HUD. Uses dynamic width to fit the label.
        """
        label = "TURN SKIPPED"
        ts = self._font_small.render(label, True, (245, 245, 245))
    
        # Compute anchor just to the right of the rightmost race track
        right_of_arms = getattr(self, "_hit_arms", None)
        right_of_space = getattr(self, "_hit_space", None)
        anchor_x = 24  # fallback padding if rects are missing
        if right_of_arms and right_of_space:
            anchor_x = max(right_of_arms.right, right_of_space.right) + 20
        elif right_of_arms:
            anchor_x = right_of_arms.right + 16
        elif right_of_space:
            anchor_x = right_of_space.right + 16
    
        pad_x, pad_y = 12, 6
        w = ts.get_width() + pad_x * 2 + 18
        h = max(26, ts.get_height() + pad_y * 2)
        y = (self.HEIGHT - h) // 2
    
        # Banner surface
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        rect = surf.get_rect()
        # Red pill with subtle border
        pygame.draw.rect(surf, (175, 45, 45, 230), rect, border_radius=10)
        pygame.draw.rect(surf, (255, 255, 255, 90), rect, 1, border_radius=10)
    
        # Warning triangle at left
        tri_x = 10
        tri = [(tri_x, h//2 - 6), (tri_x + 10, h//2 - 6), (tri_x + 5, h//2 + 6)]
        pygame.draw.polygon(surf, (255, 220, 120), tri)
        pygame.draw.polygon(surf, (60, 40, 20), tri, 1)
        # Exclamation
        pygame.draw.line(surf, (60, 40, 20), (tri_x + 5, h//2 - 3), (tri_x + 5, h//2 + 2), 2)
        pygame.draw.circle(surf, (60, 40, 20), (tri_x + 5, h//2 + 5), 1)
    
        # Text
        surf.blit(ts, (pad_x + 14, (h - ts.get_height()) // 2))
    
        # Blit to main surface
        self.surface.blit(surf, (anchor_x, y))

    def _draw_defcon(self) -> None:
        box = self._defcon_rect
        pygame.draw.rect(self.surface, (38, 46, 62), box, border_radius=10)
        pygame.draw.rect(self.surface, (255, 255, 255, 36), box, 1, border_radius=10)
        title = self._font_small.render("DEFCON", True, (182, 190, 200))
        self.surface.blit(title, (box.x + 12, box.y + 6))
        y = box.y + 6 + title.get_height() + 4
        size = 20
        gap = 8

        # draw 5 squares labeled 5..1 left->right (safe -> danger)
        squares = []
        for i, lvl in enumerate([5, 4, 3, 2, 1]):
            r = pygame.Rect(box.x + 12 + i * (size + gap), y, size, size)
            squares.append((r, lvl))
            base_col = (64, 76, 96)
            pygame.draw.rect(self.surface, base_col, r, border_radius=6)
            pygame.draw.rect(self.surface, (255, 255, 255, 30), r, 1, border_radius=6)

        cur_rect = None
        for r, lvl in squares:
            if lvl == self.defcon:
                cur_rect = r
                break
        if cur_rect:
            # danger line to the LEFT of the current box
            left_start = box.x + 12
            danger_rect = pygame.Rect(
                left_start,
                cur_rect.y + cur_rect.h // 2 - 3,
                max(0, cur_rect.left - left_start - 4),
                6,
            )
            if danger_rect.w > 0:
                pygame.draw.rect(self.surface, (160, 50, 50), danger_rect, border_radius=3)

        for r, lvl in squares:
            if lvl == self.defcon:
                fill = self._defcon_color(lvl)
                pygame.draw.rect(self.surface, fill, r.inflate(-4, -4), border_radius=4)
                pygame.draw.rect(self.surface, (255, 255, 255, 50), r, 2, border_radius=6)
            else:
                if cur_rect and r.left < cur_rect.left:
                    shade = (110, 60, 60)
                else:
                    shade = (72, 80, 96)
                pygame.draw.rect(self.surface, shade, r.inflate(-6, -6), border_radius=4)

        num = self._font_big.render(str(self.defcon), True, (236, 241, 246))
        self.surface.blit(num, (box.right - num.get_width() - 16, box.y + (box.h - num.get_height()) // 2))
        self._hit_defcon = box.copy()

    def _defcon_color(self, lvl: int) -> tuple[int, int, int]:
        palette_by_level = {
            5: GREEN,
            4: (150, 180, 80),
            3: ORANGE,
            2: (220, 90, 60),
            1: RED,
        }
        return palette_by_level[max(1, min(5, int(lvl)))]

    # -------------------------- Hover Help --------------------------
    def _update_hover(self, mouse: Tuple[int, int]) -> None:
        self._hover = None
        if self._hit_pp.collidepoint(mouse):
            self._hover = ("Political Power — spendable resources for actions.", mouse)
        elif self._hit_war.collidepoint(mouse):
            self._hover = ("War Power — modifies war odds and outcomes.", mouse)
        elif self._hit_arms.collidepoint(mouse):
            if self._arms_lock > 0:
                self._hover = (f"Arms Race — LOCKED for {self._arms_lock} turns.", mouse)
            else:
                self._hover = ("Arms Race — click to open upgrade menu.", mouse)
        elif self._hit_space.collidepoint(mouse):
            self._hover = ("Space Race — click to open upgrade menu.", mouse)
        elif self._hit_defcon.collidepoint(mouse):
            self._hover = ("DEFCON — global tension (1=Thermonuclear war risk, 5=Stable).", mouse)

    def _draw_tooltip(self) -> None:
        if not self._hover:
            return
        text, pos = self._hover
        ts = self._hint_font.render(text, True, (236, 241, 246))
        pad_x, pad_y = 10, 6
        w, h = ts.get_width() + pad_x * 2, ts.get_height() + pad_y * 2
        x, y = pos[0] + 14, max(6, pos[1] - h - 10)
        sw, sh = self.surface.get_size()
        if x + w > sw - 6:
            x = sw - w - 6
        if y < 6:
            y = pos[1] + 18
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (24, 30, 36), panel.get_rect(), border_radius=6)
        pygame.draw.rect(panel, (180, 186, 192), panel.get_rect(), 1, border_radius=6)
        pygame.draw.line(panel, ACCENT, (6, 5), (w - 6, 5), 2)
        panel.blit(ts, (pad_x, pad_y))
        self.surface.blit(panel, (x, y))


    def _chip_size(self, text: str) -> Tuple[int, int]:
        pad_x, pad_y = 12, 6
        ts = self._font_small.render(text, True, (230, 235, 242))
        w, h = ts.get_width() + pad_x * 2 + 18, ts.get_height() + pad_y * 2
        return w, h

    def _left_start(self) -> int:
        if self.subject_name:
            w, _ = self._chip_size(self.subject_name)
            return 12 + w + 36  # extra padding to avoid overlap
        return 36

    def _bloc_color_for_current(self) -> Tuple[int, int, int]:
        name = (self._bloc_name or "").strip()
        return BLOC_COLORS.get(name, BLOC_COLORS["Non-Aligned"])

# -------------------------- Demo (TopBar + Map) --------------------------
# This demo shows the HUD pinned at the top and the MapManager below it. Clicking a country
# updates the HUD to that country. Clicking the Arms/Space capsules prints a placeholder.

if __name__ == "__main__":
    import sys
    try:
        # Local modules the user already has
        from map import MapManager  # requires assets/world_idmap.png + assets/id_to_country.json
        from models import Country, Bloc
    except Exception as e:
        print("Could not import map/models modules:", e)
        sys.exit(1)

    pygame.init()
    tooltip_font = pygame.font.SysFont("consolas,menlo,dejavusansmono,monospace", 18)

    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    clock = pygame.time.Clock()
    pygame.display.set_caption("Cold War HUD + Map Demo; click Arms/Space")

    # Minimal playable set — use names that exist in your id_to_country.json
    blocs, countries = init_countries_and_blocs()

    # Managers
    def on_click_arms(name: Optional[str]):
        print(f"[TopBar] Arms menu placeholder for: {name}")

    def on_click_space(name: Optional[str]):
        print(f"[TopBar] Space menu placeholder for: {name}")
        
    Game = GameState(screen, blocs, countries, countries["USSR"])
    Game.country("USSR").arms_race = 2
    Game.change_defcon(-1)
    
    hud = TopBarManager(screen, Game, on_click_arms=on_click_arms, on_click_space=on_click_space)

    # Map sits below the HUD; create a subsurface for it by drawing against the main screen,
    # but ensure we leave HUD area untouched and pass clicks/coords in full screen space.
    # MapManager already takes the full screen, so we'll just offset our own drawing below HUD.
    # Easiest: let MapManager render to full screen; we draw HUD last so it overlays cleanly.

    mmap = MapManager(screen, countries, tooltip_font)
    
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                Game.country("USSR").arms_race = 3
                Game.country("USSR").space_race = 2
                Game.country("USSR").pp = 100
                Game.country("USSR").turn_skip = 3
                Game.arms_race_lock = 3
                Game.defcon = 2


            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                hud.surface = screen
                hud.on_resize(event.size)
                mmap.surface = screen
            # feed events to both (order: map first so bar hovers win on top)
            mmap.handle_event(event)
            hud.handle_event(event)

        # draw world
        mmap.draw()

        # draw HUD last so it overlays the top nicely
        hud.draw()

        pygame.display.flip()

    pygame.quit()
