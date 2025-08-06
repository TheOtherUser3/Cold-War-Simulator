"""pointer_spinner.py – Central‑pointer spinner for 7 coup outcomes

Revision 3.1 – finished implementation
-------------------------------------
• Static 7‑wedge wheel; text always readable.
• Small hub circle with blue cap.
• Isosceles‑triangle pointer (wider base) sits on hub rim; only pointer spins.
• One click → spin (ease‑out cubic); next click → dismiss overlay.
• Public API: `SpinnerManager.start_spin(on_result, spinner=None)`.
• Stand‑alone demo: run `python pointer_spinner.py`, press <SPACE> to summon spinner.
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

    # ---------- External API ----------

    def start_spin(
        self,
        *,
        on_result: Callable[[int, str], None] | None = None,
        spinner: Spinner | None = None,
    ) -> None:
        """Show overlay and wait for first click to spin."""
        if spinner is not None:
            self.spinner = spinner
        if self.spinner is None:
            raise ValueError("SpinnerManager: no Spinner set")
        if self.state != "IDLE":
            return  # already visible
        self._build_wheel()
        self.state = "WAIT"
        self._cb = on_result

    # ---------- Main‑loop hooks ----------

    def handle_event(self, ev: pygame.event.Event) -> None:
        if self.state == "IDLE":
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.state == "WAIT":
                self._begin_spin()
            elif self.state == "SHOW":
                self.state = "IDLE"
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.state = "IDLE"

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
            if self._cb:
                self._cb(self._result_idx, self.spinner.labels[self._result_idx])

    def draw(self) -> None:
        if self.state == "IDLE":
            return
        cx, cy = self.screen.get_width() // 2, self.screen.get_height() // 2
        # dim backdrop
        self.screen.blit(self._overlay, (0, 0))
        # wheel
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
        # instructions
        msg = "Click to spin" if self.state == "WAIT" else "Click to continue"
        txt = self.font.render(msg, True, WHITE)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy + self.radius + 50)))
        
    def is_active(self) -> bool:
        return self.state != self.IDLE

    # ---------- Internals ----------

    def _begin_spin(self) -> None:
        self.state = "SPIN"
        self._elapsed = 0.0
        self._start_angle = 0.0  # always start pointing up
        self._result_idx = random.randrange(self.spinner.n)
        mid_deg = -90 + (self._result_idx + 0.5) * self.spinner.angle_per
        extra_turns = random.randint(4, 6) * 360
        self._target_angle = mid_deg + extra_turns

    # --------------------------------------------------
    # Rendering helpers
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
    screen = pygame.display.set_mode((900, 700))
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
                mgr.start_spin()
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
