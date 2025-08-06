import pygame
import random
from typing import Optional, Tuple, Callable

# --------------------------------------------------
# DEFCON COIN — Slim version (no wrapper, no queue)
# * Animation fix preserved (no implicit end flip)
# * Restored prettier coin graphics + "DEFCON COIN" title
# * Surprise flip still happens post-stop with 35% chance
# --------------------------------------------------

Color = Tuple[int, int, int]

# ---------------------- EASING ----------------------

def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    p = t - 1.0
    return 1.0 + p * p * p

# ---------------------- FACE RENDERING ----------------------

class CoinFace:
    """Renders a circular, beveled coin with centered text.

    style="nice" → friendly gold/green, soft shadow
    style="scary" → harsh red/black, optional rim spikes + text glow
    """

    def __init__(
        self,
        label: str,
        *,
        style: str = "nice",
        font_name: Optional[str] = None,
        font_size: int = 48,
    ):
        self.label = label
        self.style = style
        self.font_name = font_name
        self.font_size = font_size

    def _ring(self, surf: pygame.Surface, color: Color, radius: int, width: int, alpha: int = 255):
        c = (*color, alpha)
        pygame.draw.circle(surf, c, (surf.get_width() // 2, surf.get_height() // 2), radius, width)

    def _radial(self, surf: pygame.Surface, inner: Color, outer: Color):
        cx, cy = surf.get_width() // 2, surf.get_height() // 2
        r = min(cx, cy)
        for i in range(r, 0, -1):
            t = i / r
            col = (
                int(inner[0] * t + outer[0] * (1 - t)),
                int(inner[1] * t + outer[1] * (1 - t)),
                int(inner[2] * t + outer[2] * (1 - t)),
            )
            pygame.draw.circle(surf, col, (cx, cy), i)

    def render(self, size: Tuple[int, int]) -> pygame.Surface:
        w, h = size
        r = min(w, h) // 2
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2

        if self.style == "nice":
            base_inner = (245, 220, 120)
            base_outer = (185, 150, 60)
            rim_dark = (120, 95, 40)
            text_col = (25, 55, 35)
            shadow_col = (0, 0, 0, 100)
        else:
            base_inner = (240, 70, 70)
            base_outer = (120, 20, 20)
            rim_dark = (30, 0, 0)
            text_col = (10, 10, 10)
            shadow_col = (0, 0, 0, 160)

        body = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        self._radial(body, base_inner, base_outer)
        self._ring(body, (255, 255, 255), r - 2, 2, 70)
        self._ring(body, rim_dark, r - 1, 2, 180)
        self._ring(body, (255, 255, 255), int(r * 0.78), 2, 40)
        self._ring(body, rim_dark, int(r * 0.75), 2, 160)

        # Optional spiky rim for scary side
        if self.style == "scary":
            spikes = pygame.Surface(body.get_size(), pygame.SRCALPHA)
            import math
            N = 32
            for k in range(N):
                ang = (2 * math.pi * k) / N
                out = (cx + int((r - 4) * math.cos(ang)), cy + int((r - 4) * math.sin(ang)))
                mid = (cx + int((r - 16) * math.cos(ang + 0.04)), cy + int((r - 16) * math.sin(ang + 0.04)))
                inn = (cx + int((r - 26) * math.cos(ang - 0.04)), cy + int((r - 26) * math.sin(ang - 0.04)))
                pygame.draw.polygon(spikes, (40, 0, 0, 120), [out, mid, inn])
            body.blit(spikes, (0, 0))

        # Fit label
        max_w = int(r * 1.3)
        max_h = int(r * 0.9)
        size_px = self.font_size
        font = pygame.font.Font(self.font_name, size_px)
        text = self.label.upper()
        while size_px > 16 and (font.size(text)[0] > max_w or font.size(text)[1] > max_h):
            size_px -= 1
            font = pygame.font.Font(self.font_name, size_px)

        txt = font.render(text, True, text_col)
        if shadow_col[3] > 0:
            sh = font.render(text, True, shadow_col[:3])
            body.blit(sh, (cx - sh.get_width() // 2 + 2, cy - sh.get_height() // 2 + 2))
        if self.style == "scary":
            glow = pygame.Surface(txt.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 60, 60, 80), glow.get_rect(), border_radius=6)
            body.blit(glow, (cx - glow.get_width() // 2, cy - glow.get_height() // 2))
        body.blit(txt, (cx - txt.get_width() // 2, cy - txt.get_height() // 2))

        surf.blit(body, (cx - r, cy - r))
        return surf

# ---------------------- COIN MODEL ----------------------

class Coin:
    """Two-sided coin. Index 0 = RAISE, 1 = LOWER for convenience."""

    def __init__(self, raise_face: CoinFace, lower_face: CoinFace):
        self.faces = [raise_face, lower_face]

    @classmethod
    def defcon(cls) -> "Coin":
        return cls(CoinFace("RAISE", style="nice"), CoinFace("LOWER", style="scary"))

    def get(self, idx: int) -> CoinFace:
        return self.faces[idx]

# ---------------------- ANIMATION CORE ----------------------

class CoinFlipAnimation:
    """Monotonic Y-flip with easing.

    - Integer number of half-flips with parity adjusted to land on target face.
    - Width squashes with |cos(theta)|; swap face at every pi crossing.
    - Soft scale bounce near the end.
    - HARD FIX retained: we *force* the final face during a pre-lock window
      **before** the stop, then keep it through the end-lock window. This
      guarantees *no* face change at/after the stop unless the surprise flips.
    """

    def __init__(
        self,
        coin: Coin,
        size: int = 220,
        duration_ms: int = 1100,
        half_flips: Optional[int] = None,
        bounce_scale: float = 0.12,
        *,
        final_face_lock_ms: int = 160,
        final_face_prelock_ms: int = 260,
    ):
        assert final_face_lock_ms >= 0 and final_face_prelock_ms >= 0
        self.coin = coin
        self.size = size
        self.duration_ms = duration_ms
        self.bounce_scale = bounce_scale
        self.half_flips = half_flips or random.randint(6, 10)
        # Clamp windows to fit in duration
        total_pre = min(final_face_prelock_ms, max(0, duration_ms - 50))
        total_lock = min(final_face_lock_ms, max(0, duration_ms - total_pre))
        self.final_face_prelock_ms = total_pre
        self.final_face_lock_ms = total_lock

        self.elapsed = 0
        self.running = False
        self.current_idx = random.randint(0, 1)
        self.result_idx: Optional[int] = None
        self.result_text: Optional[str] = None
        self._forced: Optional[int] = None
        self._surf_raise = self.coin.get(0).render((self.size, self.size))
        self._surf_lower = self.coin.get(1).render((self.size, self.size))

    def start(self, force_index: Optional[int] = None):
        self.elapsed = 0
        self.running = True
        self._forced = force_index
        final_idx = self._forced if self._forced is not None else random.randint(0, 1)
        # Ensure parity lands on final face
        if (self.current_idx ^ (self.half_flips & 1)) != final_idx:
            self.half_flips += 1
        self.result_idx = final_idx
        self.result_text = "RAISE" if final_idx == 0 else "LOWER"

    def update(self, dt_ms: int):
        if not self.running:
            return
        self.elapsed += dt_ms
        if self.elapsed >= self.duration_ms:
            self.elapsed = self.duration_ms
            self.running = False
            if self.result_idx is not None:
                self.current_idx = self.result_idx

    def draw(self, screen: pygame.Surface, center: Tuple[int, int]):
        cx, cy = center
        t = min(self.elapsed / self.duration_ms, 1.0)
        eased = ease_out_cubic(t)
        import math
        theta = eased * (self.half_flips * math.pi)  # 0 → Nπ

        # Completed half-flips; epsilon avoids boundary jitter
        k = int((theta + 1e-5) // math.pi)
        parity_face = (self.current_idx + (k & 1)) & 1

        # Timing windows
        lock_t = 1.0 - (self.final_face_lock_ms / self.duration_ms)
        pre_t = max(0.0, lock_t - (self.final_face_prelock_ms / self.duration_ms))

        # Force the face to the result from pre_t onward
        if (self.result_idx is not None) and (t >= pre_t):
            face_idx = self.result_idx
        else:
            face_idx = parity_face

        face_surf = self._surf_raise if face_idx == 0 else self._surf_lower
        w0, h0 = face_surf.get_size()

        squash = max(0.06, abs(math.cos(theta)))
        scale = 1.0 + self.bounce_scale * (1.0 - ease_out_cubic(t))
        draw_w = max(2, int(w0 * squash * scale))
        draw_h = int(h0 * scale)
        scaled = pygame.transform.smoothscale(face_surf, (draw_w, draw_h))
        rect = scaled.get_rect(center=(cx, cy))

        if squash < 0.22:
            edge = pygame.Surface((int(w0 * 0.06), h0), pygame.SRCALPHA)
            pygame.draw.rect(edge, (220, 200, 120, 200), edge.get_rect(), border_radius=3)
            e_rect = edge.get_rect(center=(cx, cy))
            screen.blit(edge, e_rect)
        screen.blit(scaled, rect)

# ---------------------- MODAL MANAGER (no queue) ----------------------

class CoinManager:
    IDLE = 0
    AWAIT_CLICK = 1
    FLIPPING = 2
    SHOWING = 3

    def __init__(
        self,
        surface: pygame.Surface,
        coin_size: int = 220,
        dim_background: bool = True,
    ):
        self.surface = surface
        self.coin_size = coin_size
        self.dim_background = dim_background
        self._dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 160))

        self.state = self.IDLE
        self.anim: Optional[CoinFlipAnimation] = None
        self._prompt_surf: Optional[pygame.Surface] = None
        self._prompt_close: Optional[pygame.Surface] = None
        self.on_result: Optional[Callable[[int, str], None]] = None
        self.rect = pygame.Rect(0, 0, coin_size, coin_size)
        self.rect.center = surface.get_rect().center

        # Title (restored)
        self._font_title = pygame.font.SysFont("Impact", 56, bold=False)
        self._title_surf: Optional[pygame.Surface] = None
        self._title_rect: Optional[pygame.Rect] = None
        self._build_title()

        # Prompts
        self._font_prompt = pygame.font.SysFont("Segoe UI", 28, bold=True)

        # Surprise post-stop flip settings
        self.surprise_prob = 0.35
        self._surprise_timer_ms = 0
        self._show_face_idx = 0
        self._will_surprise = False
        self._post_stage = None  # None=not active, 0=hold stop-frame, 2=done

    # ---------- Public API ----------
    def start_flip(self, coin: Coin, on_result: Optional[Callable[[int, str], None]] = None, *, force_index: Optional[int] = None, auto_flip: bool = False) -> bool:
        if self.is_active():
            return False
        self.anim = CoinFlipAnimation(coin, size=self.rect.width)
        self.on_result = on_result
        self.state = self.AWAIT_CLICK
        self._prompt_surf = self._render_prompt("Click to FLIP")
        self._prompt_close = None
        # reset surprise state
        self._surprise_timer_ms = 0
        self._show_face_idx = 0
        self._will_surprise = False
        self._post_stage = None
        if auto_flip and self.anim:
            self.anim.start(force_index)
            self.state = self.FLIPPING
        return True

    def is_active(self) -> bool:
        return self.state != self.IDLE

    # ---------- Events / update ----------
    def handle_event(self, event: pygame.event.Event):
        if self.state == self.IDLE:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.state == self.AWAIT_CLICK and self.anim:
                self.anim.start()
                self.state = self.FLIPPING
                return
            if self.state == self.SHOWING and self._prompt_close is not None:
                # capture and teardown, then callback
                idx = self.anim.result_idx if self.anim else None
                label = self.anim.result_text if self.anim else None
                cb = self.on_result
                self.anim = None
                self.on_result = None
                self.state = self.IDLE
                if cb is not None and idx is not None and label is not None:
                    cb(idx, label)
                return

    def update(self, dt: float):
        # Handle spinning
        if self.state == self.FLIPPING and self.anim is not None:
            self.anim.update(int(dt * 1000))
            if not self.anim.running:
                # Spin finished → show the stop-frame (which equals result face) for a short hold.
                self.state = self.SHOWING
                self._post_stage = 0  # start hold
                self._surprise_timer_ms = 240
                self._will_surprise = (random.random() < self.surprise_prob)
                self._show_face_idx = (self.anim.result_idx or 0)
                self._prompt_close = None
            return

        # Post-stop HOLD and optional one-time SURPRISE
        if self.state == self.SHOWING and self._post_stage == 0:
            self._surprise_timer_ms -= int(dt * 1000)
            if self._surprise_timer_ms <= 0:
                # One-time decision already made; now apply it and finish.
                if self._will_surprise and self.anim is not None:
                    new_idx = 1 - (self.anim.result_idx or 0)
                    self.anim.result_idx = new_idx
                    self.anim.result_text = "RAISE" if new_idx == 0 else "LOWER"
                    self._show_face_idx = new_idx
                # reveal continue button (match color to final face)
                color = (60, 160, 95) if (self.anim and self.anim.result_idx == 0) else (200, 50, 50)
                self._prompt_close = self._render_prompt("Click to CONTINUE", bg=color)
                self._post_stage = 2
            return

    # ---------- Draw ----------
    def draw(self):
        if self.state == self.IDLE:
            return

        if self.dim_background:
            self.surface.blit(self._dim, (0, 0))

        # Title (restored)
        if self._title_surf and self._title_rect:
            self.surface.blit(self._title_surf, self._title_rect)

        # Coin / prompts
        if self.state in (self.AWAIT_CLICK, self.SHOWING):
            if self.state == self.AWAIT_CLICK:
                coin_surf = self._prompt_surf
                if coin_surf:
                    rect = coin_surf.get_rect(center=self.rect.center)
                    self.surface.blit(coin_surf, rect)
            else:
                if self.anim:
                    idx = self._show_face_idx if self._post_stage is not None else (self.anim.result_idx or 0)
                    face = self.anim._surf_raise if idx == 0 else self.anim._surf_lower
                    rect = face.get_rect(center=self.rect.center)
                    self.surface.blit(face, rect)
                if self._prompt_close:
                    prect = self._prompt_close.get_rect()
                    prect.centerx = self.rect.centerx
                    prect.top = self.rect.bottom + 40
                    self.surface.blit(self._prompt_close, prect)
        elif self.state == self.FLIPPING and self.anim:
            self.anim.draw(self.surface, self.rect.center)

    # ---------- Resizing ----------
    def on_resize(self, size: Tuple[int, int]):
        self._dim = pygame.Surface(size, pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 160))
        self.rect.center = pygame.Rect((0, 0), size).center
        self._build_title()
        if self.state == self.AWAIT_CLICK:
            self._prompt_surf = self._render_prompt("Click to FLIP")

    # ---------- Internals ----------
    def _render_prompt(self, text: str, bg: Optional[Color] = None) -> pygame.Surface:
        pad_x, pad_y = 16, 10
        ts = self._font_prompt.render(text, True, (20, 20, 25))
        surf = pygame.Surface((ts.get_width() + pad_x * 2, ts.get_height() + pad_y * 2), pygame.SRCALPHA)
        color = bg or (230, 210, 110)
        pygame.draw.rect(surf, color, surf.get_rect(), border_radius=12)
        pygame.draw.rect(surf, (255, 255, 255, 40), surf.get_rect(), 2, border_radius=12)
        surf.blit(ts, (pad_x, pad_y))
        return surf

    def _build_title(self):
        txt = "DEFCON COIN"
        ts = self._font_title.render(txt, True, (210, 50, 50))
        light = self._font_title.render(txt, True, (255, 240, 240))
        dark = self._font_title.render(txt, True, (20, 20, 24))
        w = ts.get_width() + 18
        h = ts.get_height() + 20
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.blit(dark, (9, 11))
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            surf.blit(light, (9 + dx, 9 + dy))
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            surf.blit(dark, (9 + dx, 9 + dy))
        surf.blit(ts, (9, 9))
        self._title_surf = surf
        rect = surf.get_rect()
        rect.centerx = self.surface.get_rect().centerx
        rect.top = 12
        self._title_rect = rect

# ---------------------- Demo ----------------------

def demo():
    pygame.init()
    screen = pygame.display.set_mode((960, 540), pygame.RESIZABLE)
    clock = pygame.time.Clock()
    pygame.display.set_caption("DEFCON COIN Demo — press C to open; click to flip/continue")

    mgr = CoinManager(screen)

    def on_coin(idx: int, label: str):
        print("COIN:", idx, label)

    running = True
    font = pygame.font.Font(None, 28)

    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_c:
                    mgr.start_flip(Coin.defcon(), on_coin)
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                mgr.surface = screen
                mgr.on_resize(event.size)
            mgr.handle_event(event)

        mgr.update(dt)
        screen.fill((18, 18, 26))
        y = 16
        for line in [
            "Press C to open the DEFCON COIN",
            "Click once to flip; click again to continue",
            "ESC to quit",
        ]:
            t = font.render(line, True, (235, 235, 240))
            screen.blit(t, (16, y))
            y += 28

        mgr.draw()
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    demo()
