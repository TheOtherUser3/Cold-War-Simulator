import pygame
import random
import math
from typing import Callable, List, Sequence, Optional, Tuple, Union

# --------------------------------------------------
# Fancy Dice System for Pygame (Enhanced Visuals)
# --------------------------------------------------

Color = Tuple[int, int, int]

DICE_COLORS = [
    (220, 62, 62),    # Red
    (253, 203, 88),   # Yellow
    (66, 170, 255),   # Blue
    (98, 206, 115),   # Green
    (232, 112, 255),  # Purple
    (255, 153, 51),   # Orange
]

# ---------------------- EASING ----------------------

def ease_out_back(t: float, s: float = 1.5) -> float:
    t -= 1
    return t * t * ((s + 1) * t + s) + 1

# ---------------------- DATA ------------------------

class DiceFace:
    """Represents one face with improved visual design."""
    def __init__(
        self,
        text: str,
        face_index: int = 0,
        font_name: Optional[str] = None,
        font_size: int = 28,
        wrap_width: int = 18,
        bg_color: Optional[Tuple[int,int,int]] = None,
    ):
        self.text = text
        self.text_color = (0, 0, 0)  # Always black text
        self.bg_color = bg_color if bg_color is not None else DICE_COLORS[face_index % len(DICE_COLORS)]
        self.face_index = face_index
        self.font_name = font_name
        self.font_size = font_size
        self.wrap_width = wrap_width

    def _wrap(self, text: str) -> List[str]:
        words = text.split()
        lines: List[str] = []
        cur: List[str] = []
        for w in words:
            test = " ".join(cur + [w])
            if len(test) > self.wrap_width:
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
            else:
                cur.append(w)
        if cur:
            lines.append(" ".join(cur))
        if not lines:
            lines = [""]
        return lines

    def render(self, size: Tuple[int, int]) -> pygame.Surface:
        w, h = size
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # Main fill with gradient
        self.draw_gradient(surf, self.bg_color, (255,255,255), vertical=True)
        # Border
        pygame.draw.rect(surf, (20, 20, 20), surf.get_rect(), 5, border_radius=20)
        # Rounded corner inner highlight
        pygame.draw.rect(surf, (255,255,255,40), surf.get_rect().inflate(-10,-10), 3, border_radius=16)
        # Text
        font = pygame.font.Font(self.font_name, self.font_size)
        lines = self._wrap(self.text)
        rendered = [font.render(line, True, self.text_color) for line in lines]
        total_h = sum(r.get_height() for r in rendered)
        y = (h - total_h) // 2
        for r in rendered:
            x = (w - r.get_width()) // 2
            surf.blit(r, (x, y))
            y += r.get_height()
        return surf

    def draw_gradient(self, surf, color1, color2, vertical=True):
        w, h = surf.get_size()
        for i in range(h if vertical else w):
            blend = i / (h-1 if vertical else w-1)
            c = tuple(int(color1[j] * (1-blend) + color2[j] * blend) for j in range(3))
            if vertical:
                pygame.draw.line(surf, c, (0,i), (w-1,i))
            else:
                pygame.draw.line(surf, c, (i,0), (i,h-1))

class Dice:
    def __init__(self, faces: Sequence[DiceFace]):
        if not faces:
            raise ValueError("Dice must have at least one face")
        self.faces: List[DiceFace] = list(faces)

    def face_count(self) -> int:
        return len(self.faces)

    def random_index(self) -> int:
        return random.randrange(len(self.faces))

    def get_face(self, idx: int) -> DiceFace:
        return self.faces[idx]

    @classmethod
    def from_strings(cls, texts: Sequence[str], **kwargs) -> "Dice":
        faces = [DiceFace(t, face_index=i, **kwargs) for i, t in enumerate(texts)]
        return cls(faces)

# ---------------------- ANIMATION CORE ----------------------

class DiceRollAnimation:
    def __init__(
        self,
        dice: Dice,
        size: int = 180,
        duration_ms: int = 1050,
        shuffle_rate_ms: int = 60,
        spin_degrees: int = 810,
        bounce_scale: float = 0.19,
    ):
        self.dice = dice
        self.size = size
        self.duration_ms = duration_ms
        self.shuffle_rate_ms = shuffle_rate_ms
        self.spin_degrees = spin_degrees
        self.bounce_scale = bounce_scale

        self.elapsed = 0
        self.is_rolling = False
        self._next_shuffle = 0
        self.current_idx = 0
        self.result_index: Optional[int] = None
        self.result_text: Optional[str] = None
        self.result_face: Optional[DiceFace] = None
        self.current_surf: Optional[pygame.Surface] = None

    def start_roll(self, force_index: Optional[int] = None) -> None:
        self.elapsed = 0
        self.is_rolling = True
        self._next_shuffle = 0
        self.result_index = None
        self.result_text = None
        self.result_face = None
        self._forced = force_index
        self.current_idx = self.dice.random_index()
        self.current_surf = self.dice.get_face(self.current_idx).render((self.size, self.size))

    def update(self, dt_ms: int) -> None:
        if not self.is_rolling:
            return
        self.elapsed += dt_ms
        if self.elapsed >= self.duration_ms:
            self.is_rolling = False
            if self._forced is not None:
                self.result_index = self._forced
            else:
                self.result_index = self.dice.random_index()
            face = self.dice.get_face(self.result_index)
            self.result_face = face
            self.current_surf = face.render((self.size, self.size))
            self.result_text = face.text
            return

        if self.elapsed >= self._next_shuffle:
            self.current_idx = self.dice.random_index()
            self.current_surf = self.dice.get_face(self.current_idx).render((self.size, self.size))
            self._next_shuffle = self.elapsed + self.shuffle_rate_ms

    def draw(self, screen: pygame.Surface, topleft: Tuple[int, int]) -> None:
        if self.current_surf is None:
            return
        t = min(self.elapsed / self.duration_ms, 1.0)
        eased = ease_out_back(t)
        scale = 1 + self.bounce_scale * (1 - eased)
        # Always rotate in the same (clockwise) direction:
        angle = (1 - eased) * self.spin_degrees
        surf = pygame.transform.rotozoom(self.current_surf, angle, scale)
        rect = surf.get_rect(topleft=topleft)
        screen.blit(surf, rect)

# ---------------------- MODAL MANAGER ----------------------

class DiceManager:
    IDLE = 0
    AWAIT_CLICK = 1
    ROLLING = 2
    SHOWING = 3

    def __init__(
        self,
        surface: pygame.Surface,
        die_size: int = 180,
        dim_background: bool = True,
    ):
        self.surface = surface
        self.dim_background = dim_background
        self._dim_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        self._dim_surf.fill((0, 0, 0, 160))

        self.state = self.IDLE
        self.anim: Optional[DiceRollAnimation] = None
        self.on_result: Optional[Callable[[str], None]] = None

        self.rect = pygame.Rect(0, 0, die_size, die_size)
        self.rect.center = surface.get_rect().center

        self.prompt_roll = DiceFace("Click to ROLL", 0, font_size=30)
        self.prompt_close = None  # Set dynamically!
        self._prompt_surf: Optional[pygame.Surface] = None

    def start_roll(self, die: Dice, on_result: Optional[Callable[[str], None]] = None):
        self.anim = DiceRollAnimation(die, size=self.rect.width)
        self.on_result = on_result
        self.state = self.AWAIT_CLICK
        self._prompt_surf = self.prompt_roll.render(self.rect.size)
        self.prompt_close = None  # Will be set on result

    def is_active(self) -> bool:
        return self.state != self.IDLE

    def handle_event(self, event: pygame.event.Event):
        if self.state == self.IDLE:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.state == self.AWAIT_CLICK and self.anim:
                self.anim.start_roll()
                self.state = self.ROLLING
            elif self.state == self.SHOWING:
                self.state = self.IDLE
                self.anim = None
                self.on_result = None

    def update(self, dt: float):
        if self.state != self.ROLLING or self.anim is None:
            return
        self.anim.update(int(dt * 1000))
        if not self.anim.is_rolling and self.anim.result_text is not None:
            self.state = self.SHOWING
            if self.on_result:
                self.on_result(self.anim.result_text)
            # Set prompt_close to match the result face color!
            face = self.anim.result_face
            bg_color = face.bg_color if face else DICE_COLORS[0]
            self.prompt_close = DiceFace("Click to CLOSE", 0, font_size=30, bg_color=bg_color)
            self._prompt_surf = self.prompt_close.render((self.rect.width, 70))

    def draw(self):
        if self.state == self.IDLE:
            return
        if self.dim_background:
            self.surface.blit(self._dim_surf, (0, 0))

        if self.state in (self.AWAIT_CLICK, self.SHOWING):
            if self.state == self.AWAIT_CLICK:
                die_surf = self._prompt_surf
            else:
                die_surf = self.anim.current_surf if self.anim else None
            if die_surf is not None:
                rect = die_surf.get_rect(center=self.rect.center)
                self.surface.blit(die_surf, rect)
        elif self.state == self.ROLLING and self.anim:
            tl = (self.rect.left, self.rect.top)
            self.anim.draw(self.surface, tl)

        if self.state in (self.SHOWING,):
            if self._prompt_surf:
                prect = self._prompt_surf.get_rect()
                prect.centerx = self.rect.centerx
                prect.top = self.rect.bottom + 18
                self.surface.blit(self._prompt_surf, prect)

# ---------------------- DEMO ----------------------

def demo():
    pygame.init()
    screen = pygame.display.set_mode((960, 540))
    clock = pygame.time.Clock()
    pygame.display.set_caption("Fancy Dice Demo — 1/2 to open dice, click to roll/close")

    die1 = Dice.from_strings([
        "Coup d'état",
        "Proxy War",
        "Sanctions (Biting)",
        "Espionage Leak",
        "Arms Race Spike",
        "Diplomatic Breakdown",
    ])

    die2 = Dice.from_strings([
        "Oil Shock",
        "Grain Embargo",
        "Debt Crisis",
        "Stimulus Boom",
        "Trade Deal",
        "Black Market Windfall",
    ])

    mgr = DiceManager(screen)

    def on_res(txt: str):
        print("Result:", txt)

    font = pygame.font.Font(None, 28)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_1:
                    mgr.start_roll(die1, on_res)
                elif event.key == pygame.K_2:
                    mgr.start_roll(die2, on_res)
            mgr.handle_event(event)

        mgr.update(dt)

        screen.fill((25, 25, 35))
        y = 15
        for line in [
            "Press 1 or 2 to start a roll",
            "Click once to roll, click again to close",
            "ESC to quit",
        ]:
            t = font.render(line, True, (230, 230, 230))
            screen.blit(t, (15, y))
            y += 28

        mgr.draw()
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    demo()
