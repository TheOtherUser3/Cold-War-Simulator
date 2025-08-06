"""pointer_spinner.py – Central‑pointer spinner for 7 coup outcomes

Revision 4.0 — adds header UI
-------------------------------------
• Static 7‑wedge wheel; text always readable.
• Small hub circle with blue cap.
• Isosceles‑triangle pointer (wider base) sits on hub rim; only pointer spins.
• One click → spin (ease‑out cubic); next click → dismiss overlay.
• **NEW**: Header bar with title and Target → Actor chips (arrow points from Target to Actor).
• Public API: `SpinnerManager.start_spin(on_result=None, spinner=None, *, title=None, actor_name=None, target_name=None)`.
• Stand‑alone demo: run this file and press <SPACE> to summon spinner.
"""

from __future__ import annotations

import math
import random
from typing import Callable, List, Optional, Tuple

import pygame

# --------------------------------------------------
# Config (labels + colours)
# --------------------------------------------------

OPTIONS: List[str] = [
    "Failed Coup - Roll Classified Docs Die",
    "Failed Coup - Starts War",
    "Successful Coup - Roll Coup Die and Destabilize Die",
    "Failed Coup - Pay 10% extra PP",
    "Failed Coup - Roll Destabilize Die",
    "Failed Coup - Recoup coup cost",
    "Successful Coup - Roll Coup Die and Classifies Docs Die",
]

COLORS: List[Tuple[int, int, int]] = [
    (220, 38, 38),   # red
    (251, 146, 60),  # orange
    (234, 179, 8),   # yellow
    (16, 185, 129),  # green
    (59, 130, 246),  # blue
    (139, 92, 246),  # purple
    (244, 114, 182), # pink
]

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
MASK  = (0, 0, 0, 160)  # translucent backdrop
STATE = str  # alias for type hints

# --------------------------------------------------
# Spinner data (pure)
# --------------------------------------------------

class Spinner:
    """Holds labels + derived angle size."""
    def __init__(self, labels: List[str]):
        if len(labels) < 2:
            raise ValueError("Spinner needs at least two labels")
        self.labels = labels
        self.n = len(labels)
        self.angle_per = 360 / self.n

# --------------------------------------------------
# Manager (modal overlay)
# --------------------------------------------------

class SpinnerManager:
    """Shows a modal spinner overlay and handles its animation lifecycle."""

    def __init__(
        self,
        surface: pygame.Surface,
        spinner: Spinner | None = None,
        radius: int = 200,
        font_size: int = 18,
        total_spin: float = 2.8,
    ) -> None:
        self.screen = surface
        self.spinner = spinner
        self.radius = radius
        self.font = pygame.font.SysFont(None, font_size, bold=True)
        self.total_spin = total_spin  # seconds the pointer takes to stop

        # State machine
        self.state: STATE = "IDLE"  # IDLE | WAIT | SPIN | SHOW

        # Pre‑built overlay
        self._overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        self._overlay.fill(MASK)

        # Cached wheel surface (rendered once per spinner)
        self._wheel_surf: Optional[pygame.Surface] = None

        # Animation variables
        self._angle       = 0.0  # current pointer angle (degrees)
        self._start_angle = 0.0
        self._target_angle= 0.0
        self._elapsed     = 0.0

        self._result_idx  = 0
        self._cb: Optional[Callable[[int, str], None]] = None

        # Pointer geometry (up‑facing triangle, centred on hub edge)
        self._pointer_raw = self._build_pointer()

        # -------- Header UI (title + Target → Actor chips) --------
        self.roll_title: Optional[str] = None
        self.actor_name: Optional[str] = None
        self.target_name: Optional[str] = None
        self._font_title = pygame.font.SysFont("Segoe UI", 26, bold=True)
        self._font_chip  = pygame.font.SysFont("Segoe UI", 18, bold=True)
        self._header_dirty = True
        self._header_surf: Optional[pygame.Surface] = None
        self._header_rect: Optional[pygame.Rect] = None
        self._header_shadow: Optional[pygame.Surface] = None
        self._header_shadow_rect: Optional[pygame.Rect] = None

    # ---------- External API ----------

    def start_spin(
        self,
        *,
        on_result: Callable[[int, str], None] | None = None,
        spinner: Spinner | None = None,
        title: Optional[str] = None,
        actor_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> None:
        """Show overlay and wait for first click to spin.
        All args are optional to keep back‑compat.
        """
        if spinner is not None:
            self.spinner = spinner
        if self.spinner is None:
            raise ValueError("SpinnerManager: no Spinner set")
        if self.state != "IDLE":
            return  # already visible
        self._build_wheel()
        self.state = "WAIT"
        self._cb = on_result
        # header strings
        self.roll_title = title
        self.actor_name = actor_name
        self.target_name = target_name
        self._header_dirty = True

    # ---------- Main‑loop hooks ----------

    def handle_event(self, ev: pygame.event.Event) -> None:
        if self.state == "IDLE":
            return
        if ev.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode(ev.size, pygame.RESIZABLE)
            self._overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            self._overlay.fill(MASK)
            self._wheel_surf = None  # force re-render wheel
            self._header_dirty = True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.state == "WAIT":
                self._begin_spin()
            elif self.state == "SHOW":
                self.state = "IDLE"
                if self._cb:
                    self._cb(self._result_idx, self.spinner.labels[self._result_idx])

    def update(self, dt: float) -> None:
        if self.state != "SPIN":
            return
        self._elapsed += dt
        t = min(self._elapsed / self.total_spin, 1.0)
        # ease‑out cubic
        ease = 1 - (1 - t) ** 3
        self._angle = self._start_angle + ease * (self._target_angle - self._start_angle)
        if t >= 1.0:
            self.state = "SHOW"
            self._header_dirty = True  # allow color/tint change if desired

    def draw(self) -> None:
        # ensure wheel surface exists after a resize
        self._build_wheel()

        cx, cy = self.screen.get_width() // 2, self.screen.get_height() // 2
        self.screen.blit(self._overlay, (0, 0))
        self.screen.blit(self._wheel_surf, self._wheel_surf.get_rect(center=(cx, cy)))
        # pointer (rotated triangle)
        rad = math.radians(self._angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        pts = [
            (cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a) for x, y in self._pointer_raw
        ]
        pygame.draw.polygon(self.screen, WHITE, pts)
        pygame.draw.polygon(self.screen, BLACK, pts, 2)
        # hub circles
        pygame.draw.circle(self.screen, WHITE, (cx, cy), int(self.radius * 0.25))
        pygame.draw.circle(self.screen, (33, 94, 255), (cx, cy), int(self.radius * 0.08))
        pygame.draw.circle(self.screen, BLACK, (cx, cy), int(self.radius * 0.25), 2)

        # Header (top-center)
        if self._header_dirty:
            self._rebuild_header()
        if self._header_surf and self._header_rect:
            if self._header_shadow and self._header_shadow_rect:
                self.screen.blit(self._header_shadow, self._header_shadow_rect)
            self.screen.blit(self._header_surf, self._header_rect)

        # instructions: show above spinner (may sit under header on very small windows)
        msg = "Click to spin" if self.state == "WAIT" else "Click to continue"
        txt = self.font.render(msg, True, WHITE)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy - self.radius - 46)))

        # Show the result text under the pointer once spin is done
        if self.state == "SHOW":
            label = self.spinner.labels[self._result_idx]
            color = COLORS[self._result_idx % len(COLORS)]
            result_font = pygame.font.SysFont(None, 26, bold=True)
            lines = self._wrap(label, 26)
            # Box sizing
            w = max(result_font.size(line)[0] for line in lines) + 36
            h = len(lines) * result_font.get_height() + 28
            box = pygame.Rect(0, 0, w, h)
            box.center = (cx, cy + self.radius + 58)
            pygame.draw.rect(self.screen, color, box, border_radius=18)
            pygame.draw.rect(self.screen, WHITE, box, 2, border_radius=18)
            y = box.top + 14
            for line in lines:
                rtxt = result_font.render(line, True, BLACK)
                rrect = rtxt.get_rect(center=(box.centerx, y + rtxt.get_height() // 2))
                self.screen.blit(rtxt, rrect)
                y += rtxt.get_height()

    def is_active(self) -> bool:
        return self.state != "IDLE"

    # ---------- Internals ----------

    def _begin_spin(self) -> None:
        self.state = "SPIN"
        self._elapsed = 0.0
        self._start_angle = 0.0
        self._result_idx = random.randrange(self.spinner.n)

        # center of chosen wedge, measured from +x
        mid_deg = -90 + (self._result_idx + 0.5) * self.spinner.angle_per
        extra_turns = random.randint(4, 6) * 360

        # pointer's zero is up (-90°), so add +90° to align with mid_deg
        self._target_angle = (mid_deg + 90) + extra_turns

    # ---------------- Header helpers ----------------

    def _compute_header_color(self) -> Tuple[int, int, int, int]:
        # Subtle tinted panel; if showing result, tint to that wedge color
        base = (40, 46, 60)
        if self.state == "SHOW":
            r, g, b = COLORS[self._result_idx % len(COLORS)]
            r = int(0.55 * r + 0.45 * base[0])
            g = int(0.55 * g + 0.45 * base[1])
            b = int(0.55 * b + 0.45 * base[2])
            return (r, g, b, 205)
        return (*base, 205)

    def _render_chip(self, text: str, bg: Tuple[int, int, int], fg=(20, 20, 25)) -> pygame.Surface:
        pad_x, pad_y = 12, 6
        ts = self._font_chip.render(text, True, fg)
        chip = pygame.Surface((ts.get_width() + pad_x * 2, ts.get_height() + pad_y * 2), pygame.SRCALPHA)
        # soften the bg
        bg_mix = (int(0.85*bg[0]+35), int(0.85*bg[1]+35), int(0.85*bg[2]+35), 230)
        pygame.draw.rect(chip, bg_mix, chip.get_rect(), border_radius=999)
        pygame.draw.rect(chip, (255, 255, 255, 36), chip.get_rect(), width=2, border_radius=999)
        chip.blit(ts, (pad_x, pad_y))
        return chip

    def _draw_arrow(self, surf: pygame.Surface, p0: Tuple[int,int], p1: Tuple[int,int], color=(235,235,240)) -> None:
        pygame.draw.line(surf, color, p0, p1, 3)
        ang = math.atan2(p1[1]-p0[1], p1[0]-p0[0])
        size = 10
        left = (p1[0] - size*math.cos(ang) + size*0.6*math.sin(ang), p1[1] - size*math.sin(ang) - size*0.6*math.cos(ang))
        right = (p1[0] - size*math.cos(ang) - size*0.6*math.sin(ang), p1[1] - size*math.sin(ang) + size*0.6*math.cos(ang))
        pygame.draw.polygon(surf, color, [p1, left, right])

    def _rebuild_header(self) -> None:
        if not (self.roll_title or self.actor_name or self.target_name):
            self._header_surf = None
            self._header_rect = None
            self._header_shadow = None
            self._header_shadow_rect = None
            self._header_dirty = False
            return
    
        win_w, _ = self.screen.get_size()
        pad_x = 18
        pad_y = 12
        gap_y = 8
        max_w = max(420, min(int(win_w * 0.9), 1100))
    
        title_txt = (self.roll_title or "").strip()
        actor  = (self.actor_name  or "").strip()
        target = (self.target_name or "").strip()
    
        title_surf = self._font_title.render(title_txt, True, (245, 245, 250)) if title_txt else None
    
        # Chip colours: blue-ish for ACTOR, purple-ish for TARGET (stable defaults)
        act_col = (59, 130, 246)
        tgt_col = (139, 92, 246)
    
        act_chip = self._render_chip(("Actor: " + actor) if actor else "Actor", act_col)
        tgt_chip = self._render_chip(("Target: " + target) if target else "Target", tgt_col)
    
        chips_gap = 18
        chips_w = act_chip.get_width() + chips_gap + tgt_chip.get_width()
        content_w = max((title_surf.get_width() if title_surf else 0), chips_w)
        box_w = min(max_w, content_w + pad_x * 2)
    
        content_h = 0
        if title_surf:
            content_h += title_surf.get_height() + gap_y
        chips_h = max(act_chip.get_height(), tgt_chip.get_height())
        content_h += chips_h
        box_h = content_h + pad_y * 2
    
        hdr = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        color = self._compute_header_color()
    
        # Shadow
        shadow = pygame.Surface((box_w + 12, box_h + 12), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 110), shadow.get_rect(), border_radius=16)
        sh_rect = shadow.get_rect()
        sh_rect.centerx = self.screen.get_rect().centerx
        sh_rect.top = 18 + 2
    
        # Panel
        pygame.draw.rect(hdr, color, hdr.get_rect(), border_radius=14)
        pygame.draw.rect(hdr, (255, 255, 255, 36), hdr.get_rect(), width=2, border_radius=14)
    
        # Title
        y = pad_y
        if title_surf:
            x = (box_w - title_surf.get_width()) // 2
            hdr.blit(title_surf, (x, y))
            y += title_surf.get_height() + gap_y
    
        # Chips row (Actor → Target)
        chips_y = y + (chips_h - act_chip.get_height()) // 2
        act_x = (box_w - chips_w) // 2
        hdr.blit(act_chip, (act_x, chips_y))
        tgt_x = act_x + act_chip.get_width() + chips_gap
        hdr.blit(tgt_chip, (tgt_x, chips_y))
        # Arrow from Actor to Target
        p0 = (act_x + act_chip.get_width() + 6, chips_y + act_chip.get_height() // 2)
        p1 = (tgt_x - 6,                      chips_y + tgt_chip.get_height() // 2)
        self._draw_arrow(hdr, p0, p1)
    
        # Store rects
        rect = hdr.get_rect()
        rect.centerx = self.screen.get_rect().centerx
        rect.top = 18
    
        self._header_surf = hdr
        self._header_rect = rect
        self._header_shadow = shadow
        self._header_shadow_rect = sh_rect
        self._header_dirty = False

    # --------------------------------------------------
    # Rendering helpers (wheel + labels + pointer geometry)
    # --------------------------------------------------

    def _build_wheel(self) -> None:
        if self._wheel_surf is not None:
            return
        d = self.radius * 2
        surf = pygame.Surface((d, d), pygame.SRCALPHA)
        cx = cy = self.radius
        for idx, label in enumerate(self.spinner.labels):
            self._draw_wedge(surf, (cx, cy), self.radius, idx)
            self._draw_label(surf, (cx, cy), label, idx)
        pygame.draw.circle(surf, WHITE, (cx, cy), self.radius, 2)
        self._wheel_surf = surf

    def _draw_wedge(self, surf: pygame.Surface, center: Tuple[int, int], r: int, idx: int) -> None:
        ang0 = -90 + idx * self.spinner.angle_per
        ang1 = ang0 + self.spinner.angle_per
        steps = 24
        pts = [center]
        for j in range(steps + 1):
            a = math.radians(ang0 + j * (ang1 - ang0) / steps)
            pts.append((center[0] + math.cos(a) * r, center[1] + math.sin(a) * r))
        pygame.draw.polygon(surf, COLORS[idx % len(COLORS)], pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)

    def _draw_label(self, surf: pygame.Surface, center: Tuple[int, int], text: str, idx: int) -> None:
        lines = self._wrap(text, 18)
        rendered = [self.font.render(line, True, BLACK) for line in lines]
        total_h = sum(r.get_height() for r in rendered)
        ang_mid = math.radians(-90 + (idx + 0.5) * self.spinner.angle_per)
        tx = center[0] + math.cos(ang_mid) * self.radius * 0.70
        ty = center[1] + math.sin(ang_mid) * self.radius * 0.70 - total_h / 2
        for r in rendered:
            surf.blit(r, r.get_rect(center=(tx, ty + r.get_height() / 2)))
            ty += r.get_height()

    @staticmethod
    def _wrap(text: str, max_len: int) -> List[str]:
        """Simple greedy word wrap."""
        words = text.split()
        lines: List[str] = []
        cur = ""
        for w in words:
            if len(cur) + len(w) + 1 > max_len:
                lines.append(cur.strip())
                cur = w + " "
            else:
                cur += w + " "
        if cur:
            lines.append(cur.strip())
        return lines

    def _build_pointer(self) -> List[Tuple[float, float]]:
        """Return triangle pointing up (y negative), base on hub edge."""
        base_w = self.radius * 0.35  # wider base (fraction of r)
        length = self.radius * 0.45   # how far the tip extends beyond hub
        return [(-base_w / 2, 0), (base_w / 2, 0), (0, -length)]

# --------------------------------------------------
# Demo helper
# --------------------------------------------------

def demo() -> None:
    pygame.init()
    screen = pygame.display.set_mode((900, 700), pygame.RESIZABLE)
    pygame.display.set_caption("Pointer Spinner Demo")
    clock = pygame.time.Clock()

    mgr = SpinnerManager(screen, Spinner(OPTIONS))

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE and mgr.state == "IDLE":
                mgr.start_spin(title="Coup spinner", actor_name="USA", target_name="Brazil")
            mgr.handle_event(ev)

        mgr.update(dt)

        screen.fill((22, 22, 30))
        mgr.draw()
        pygame.display.flip()

    pygame.quit()

# --------------------------------------------------
# Run demo when module executed directly
# --------------------------------------------------

if __name__ == "__main__":
    demo()
