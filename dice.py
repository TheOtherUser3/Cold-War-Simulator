import pygame
import random
from typing import Optional, Tuple, Callable, List, Dict, Any, Sequence

# --------------------------------------------------
# Smooth, clockwise dice roll for Pygame
#  - Clockwise only (never reverses)
#  - Eased speed profile (accelerate → cruise → decelerate)
#  - Face changes tied to angular distance (so flips slow with the spin)
#  - Locks the final face for a clean reveal
#  - Safe on window resize (RESIZABLE)
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

def ease_out_cubic(t: float) -> float:
    # monotonic 0→1
    t = max(0.0, min(1.0, t))
    p = t - 1.0
    return 1.0 + p * p * p

def ease_out_back(t: float, s: float = 1.5) -> float:
    # for a gentle end "bounce" in scale only
    t = max(0.0, min(1.0, t))
    t -= 1
    return t * t * ((s + 1) * t + s) + 1

# ---------------------- DATA ------------------------

class DiceFace:
    """One die face with gradient card look (no pips),
    with pixel-based wrapping + auto-fit.
    """

    # Layout knobs
    BOX_W_FRAC = 0.86     # max text box width as fraction of face width
    BOX_H_FRAC = 0.82     # max text box height as fraction of face height
    LINE_GAP   = 2        # px between wrapped lines
    MIN_FONT   = 14       # minimum font size when auto-shrinking

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
        self.text_color = (0, 0, 0)
        # Remember if color was auto-picked
        self._auto_color = (bg_color is None)
        self.bg_color = bg_color if bg_color is not None else DICE_COLORS[face_index % len(DICE_COLORS)]
        self.face_index = face_index
        self.font_name = font_name
        self.font_size = font_size
        self.wrap_width = wrap_width

    # ---------------- Rendering helpers ----------------

    @staticmethod
    def _draw_gradient(surf: pygame.Surface, color1, color2, vertical=True):
        w, h = surf.get_size()
        if vertical:
            for i in range(h):
                blend = i / max(1, h - 1)
                c = (
                    int(color1[0] * (1 - blend) + color2[0] * blend),
                    int(color1[1] * (1 - blend) + color2[1] * blend),
                    int(color1[2] * (1 - blend) + color2[2] * blend),
                )
                pygame.draw.line(surf, c, (0, i), (w - 1, i))
        else:
            for i in range(w):
                blend = i / max(1, w - 1)
                c = (
                    int(color1[0] * (1 - blend) + color2[0] * blend),
                    int(color1[1] * (1 - blend) + color2[1] * blend),
                    int(color1[2] * (1 - blend) + color2[2] * blend),
                )
                pygame.draw.line(surf, c, (i, 0), (i, h - 1))

    def _wrap_by_pixels(self, font: pygame.font.Font, text: str, max_w: int) -> List[str]:
        """Greedy wrap by pixel width. Hyphenates a single too-long word."""
        words = text.split(" ")
        lines: List[str] = []
        cur = ""

        def fits(s: str) -> bool:
            return font.size(s)[0] <= max_w

        i = 0
        while i < len(words):
            w = words[i]
            test = (cur + (" " if cur else "") + w) if cur else w
            if fits(test):
                cur = test
                i += 1
                continue
            # current line can't take the new word; push current if exists
            if cur:
                lines.append(cur)
                cur = ""
                continue
            # Single word longer than max_w → hyphenate chunk-by-chunk
            piece = ""
            for ch in w:
                if fits(piece + ch + "-"):
                    piece += ch
                else:
                    # commit piece-
                    lines.append(piece + "-")
                    piece = ch
            # leftover
            cur = piece
            i += 1
        if cur:
            lines.append(cur)
        return lines

    # ---------------- Public render ----------------

    def render(self, size: Tuple[int, int]) -> pygame.Surface:
        w, h = size
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Background + frame
        self._draw_gradient(surf, self.bg_color, (255, 255, 255), vertical=True)
        pygame.draw.rect(surf, (20, 20, 20), surf.get_rect(), 5, border_radius=20)
        pygame.draw.rect(surf, (255, 255, 255, 40), surf.get_rect().inflate(-10, -10), 3, border_radius=16)

        # Auto-fit text into a centered box
        max_w = int(w * self.BOX_W_FRAC)
        max_h = int(h * self.BOX_H_FRAC)

        size_px = max(self.MIN_FONT, self.font_size)
        font = pygame.font.Font(self.font_name, size_px)
        lines = self._wrap_by_pixels(font, self.text, max_w)

        def total_height(fnt: pygame.font.Font, ls: List[str]) -> int:
            if not ls:
                return 0
            return sum(fnt.size(line)[1] for line in ls) + self.LINE_GAP * (len(ls) - 1)

        # Shrink font until the block fits height (with a touch of leeway)
        # Guard against infinite loop with MIN_FONT
        while size_px > self.MIN_FONT and total_height(font, lines) > max_h:
            size_px -= 1
            font = pygame.font.Font(self.font_name, size_px)
            lines = self._wrap_by_pixels(font, self.text, max_w)

        # Render lines centered
        block_h = total_height(font, lines)
        y = (h - block_h) // 2
        for line in lines:
            text_surf = font.render(line, True, self.text_color)
            x = (w - text_surf.get_width()) // 2
            surf.blit(text_surf, (x, y))
            y += text_surf.get_height() + self.LINE_GAP

        return surf

class Dice:
    def __init__(self, faces: Sequence[DiceFace], auto_palette: bool = True):
        if not faces:
            raise ValueError("Dice must have at least one face")
        self.faces: List[DiceFace] = list(faces)
        # Assign per-face colors by position if the face didn't specify one
        if auto_palette:
            for i, f in enumerate(self.faces):
                if getattr(f, "_auto_color", True):
                    f.face_index = i
                    f.bg_color = DICE_COLORS[i % len(DICE_COLORS)]

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
    """Smooth, clockwise, angle-synced face flips.

    Rotation progresses from 0 to -K*360° (clockwise). Face changes happen
    after each `flip_step_deg` of *actual* angular travel, so as the spin slows
    the flips slow too. During the last `lock_ms`, the face is frozen to the
    final result for a clean reveal.
    """

    def __init__(
        self,
        dice: Dice,
        size: int = 180,
        duration_ms: int = 1200,
        total_rotations: Optional[int] = None,  # full spins; default 4–6
        flip_step_deg: Optional[float] = None,  # default 360 / n
        bounce_scale: float = 0.14,
        lock_ms: int = 150,
    ):
        self.dice = dice
        self.size = size
        self.duration_ms = duration_ms
        self.total_rotations = total_rotations or random.randint(4, 6)
        self.flip_step_deg = flip_step_deg or (360.0 / dice.face_count())
        self.bounce_scale = bounce_scale
        self.lock_ms = lock_ms

        # state
        self.elapsed = 0
        self.is_rolling = False
        self._angle_target = -self.total_rotations * 360.0  # clockwise = negative
        self._angle_prev = 0.0
        self._angle_now = 0.0
        self._angle_accum = 0.0
        self._locked = False

        self.current_idx = 0
        self.result_index: Optional[int] = None
        self.result_face: Optional[DiceFace] = None
        self.result_text: Optional[str] = None
        self.current_surf: Optional[pygame.Surface] = None
        self._forced: Optional[int] = None

    def start_roll(self, force_index: Optional[int] = None) -> None:
        self.elapsed = 0
        self.is_rolling = True
        self._locked = False
        self._angle_prev = 0.0
        self._angle_now = 0.0
        self._angle_accum = 0.0
        self._forced = force_index
        # start on some face (can be anything visually)
        self.current_idx = self.dice.random_index()
        self.current_surf = self.dice.get_face(self.current_idx).render((self.size, self.size))
        self.result_index = None
        self.result_face = None
        self.result_text = None

    def _select_next_face(self) -> int:
        # simple sequential advance avoids repeats and feels "dice-like"
        return (self.current_idx + 1) % self.dice.face_count()

    def _maybe_lock_final(self):
        if self._locked:
            return
        time_left = self.duration_ms - self.elapsed
        if time_left <= self.lock_ms:
            # choose the final face
            ridx = self._forced if self._forced is not None else self.dice.random_index()
            self.result_index = ridx
            self.result_face = self.dice.get_face(ridx)
            self.result_text = self.result_face.text
            # show it now and stop further flips
            self.current_idx = ridx
            self.current_surf = self.result_face.render((self.size, self.size))
            self._locked = True

    def update(self, dt_ms: int) -> None:
        if not self.is_rolling:
            return
        self.elapsed += dt_ms
        t = self.elapsed / self.duration_ms
        if t >= 1.0:
            # ensure final reveal is in place
            if not self._locked:
                self._maybe_lock_final()
            self.is_rolling = False
            self._angle_prev = self._angle_now = self._angle_target
            return

        # progress angle (monotonic, clockwise)
        eased = ease_out_cubic(t)  # 0→1
        self._angle_now = self._angle_target * eased
        d_angle = abs(self._angle_now - self._angle_prev)
        self._angle_prev = self._angle_now

        # flip faces based on real angular travel
        self._angle_accum += d_angle
        self._maybe_lock_final()
        while not self._locked and self._angle_accum >= self.flip_step_deg:
            self.current_idx = self._select_next_face()
            self.current_surf = self.dice.get_face(self.current_idx).render((self.size, self.size))
            self._angle_accum -= self.flip_step_deg

    def draw(self, screen: pygame.Surface, topleft: Tuple[int, int]) -> None:
        if self.current_surf is None:
            return
        # visual scale bounce near the end only
        t = min(self.elapsed / self.duration_ms, 1.0)
        s_eased = ease_out_back(t)
        scale = 1.0 + self.bounce_scale * (1.0 - s_eased)
        surf = pygame.transform.rotozoom(self.current_surf, self._angle_now, scale)
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
        self.on_result: Optional[Callable[[int, str], None]] = None

        self.rect = pygame.Rect(0, 0, die_size, die_size)
        self.rect.center = surface.get_rect().center

        # prompts
        self.prompt_roll = DiceFace("Click to ROLL", 0, font_size=30)
        self.prompt_close: Optional[DiceFace] = None
        self._prompt_surf: Optional[pygame.Surface] = None

        # header (dice title + Actor → Target chips)
        self.roll_title: Optional[str] = None
        self.actor_name: Optional[str] = None
        self.target_name: Optional[str] = None
        self._font_title = pygame.font.SysFont("Segoe UI", 26, bold=True)
        self._font_meta = pygame.font.SysFont("Segoe UI", 18)
        self._font_chip = pygame.font.SysFont("Segoe UI", 18, bold=True)
        self._header_dirty = True
        self._header_surf: Optional[pygame.Surface] = None
        self._header_rect: Optional[pygame.Rect] = None

        # queue of pending rolls (FIFO)
        self._pending: List[Tuple['Dice', Optional[Callable[[int, str], None]], Dict[str, Any]]] = []

    # ---------------- RESIZING ----------------
    def on_resize(self, size: Tuple[int, int]) -> None:
        self._dim_surf = pygame.Surface(size, pygame.SRCALPHA)
        self._dim_surf.fill((0, 0, 0, 160))
        self.rect.center = pygame.Rect((0, 0), size).center
        # rebuild prompt (width depends on die size)
        if self.state in (self.AWAIT_CLICK, self.SHOWING):
            if self.state == self.AWAIT_CLICK:
                self._prompt_surf = self.prompt_roll.render(self.rect.size)
            elif self.prompt_close is not None:
                self._prompt_surf = self.prompt_close.render((self.rect.width, 70))
        self._header_dirty = True

    # --------------- PUBLIC API ---------------
    def start_roll(
        self,
        die: 'Dice',
        on_result: Optional[Callable[[int, str], None]] = None,
        *,
        title: Optional[str] = None,
        actor_name: Optional[str] = None,
        target_name: Optional[str] = None,
        auto_spin: bool = False,
    ):
        """Start a new roll, or enqueue if one is already active."""
        if self.is_active():
            # enqueue instead of stomping the current modal
            self._pending.append((die, on_result, {
                'title': title, 'actor_name': actor_name, 'target_name': target_name, 'auto_spin': auto_spin
            }))
            return

        # animation
        self.anim = DiceRollAnimation(die, size=self.rect.width)
        self.on_result = on_result
        self.state = self.AWAIT_CLICK
        self._prompt_surf = self.prompt_roll.render(self.rect.size)
        self.prompt_close = None
        # header strings
        self.roll_title = title
        self.actor_name = actor_name
        self.target_name = target_name
        self._header_dirty = True

        # optional immediate spin
        if auto_spin and self.anim:
            self.anim.start_roll()
            self.state = self.ROLLING

    def queue_roll(self, die: 'Dice', on_result: Optional[Callable[[int, str], None]] = None, **kw):
        """Explicitly enqueue a roll. Starts immediately if idle."""
        if self.is_active():
            self._pending.append((die, on_result, kw))
        else:
            self.start_roll(die, on_result, **kw)

    def is_active(self) -> bool:
        return self.state != self.IDLE

    # --------------- EVENTS/UPDATE ---------------
    def handle_event(self, event: pygame.event.Event):
        if self.state == self.IDLE:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.state == self.AWAIT_CLICK and self.anim:
                self.anim.start_roll()
                self.state = self.ROLLING
                return
            if self.state == self.SHOWING:
                # capture result & callback
                idx = self.anim.result_index if self.anim else None
                label = self.anim.result_text if self.anim else None
                callback = self.on_result

                # TEAR DOWN FIRST
                self.state = self.IDLE
                self.anim = None
                self.on_result = None

                # callback after teardown (safe to enqueue another roll inside)
                if callback is not None and idx is not None and label is not None:
                    callback(idx, label)

                # kick next pending roll if any
                if self._pending:
                    die, cb, kw = self._pending.pop(0)
                    self.start_roll(die, cb, **kw)
                return

    def update(self, dt: float):
        if self.state != self.ROLLING or self.anim is None:
            return
        self.anim.update(int(dt * 1000))
        if not self.anim.is_rolling:
            self.state = self.SHOWING
            # close prompt color matches final face color
            face = self.anim.result_face
            bg_color = face.bg_color if face else DICE_COLORS[0]
            self.prompt_close = DiceFace("Click to CLOSE", 0, font_size=30, bg_color=bg_color)
            self._prompt_surf = self.prompt_close.render((self.rect.width, 70))

    # --------------- DRAW ----------------
    def _compute_header_color(self) -> Tuple[int, int, int, int]:
        base = (40, 46, 60)
        if self.anim and self.anim.dice and 0 <= self.anim.current_idx < self.anim.dice.face_count():
            face = self.anim.dice.get_face(self.anim.current_idx)
            r, g, b = face.bg_color
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
        import math
        ang = math.atan2(p1[1]-p0[1], p1[0]-p0[0])
        size = 10
        left = (p1[0] - size*math.cos(ang) + size*0.6*math.sin(ang), p1[1] - size*math.sin(ang) - size*0.6*math.cos(ang))
        right = (p1[0] - size*math.cos(ang) - size*0.6*math.sin(ang), p1[1] - size*math.sin(ang) + size*0.6*math.cos(ang))
        pygame.draw.polygon(surf, color, [p1, left, right])

    def _rebuild_header(self):
        # Hide if nothing to show
        if not (self.roll_title or self.actor_name or self.target_name):
            self._header_surf = None
            self._header_rect = None
            self._header_dirty = False
            return

        win_w, _ = self.surface.get_size()
        pad_x = 18
        pad_y = 12
        gap_y = 8
        max_w = max(420, min(int(win_w * 0.9), 1100))

        # Compose rows — title on top, chips row below (Actor → Target)
        title_txt = (self.roll_title or "").strip()
        actor = (self.actor_name or "").strip()
        target = (self.target_name or "").strip()

        title_surf = self._font_title.render(title_txt, True, (245, 245, 250)) if title_txt else None

        # Colors: use current face color for the ACTOR, soft complement for TARGET
        face_col = (90, 120, 200)
        if self.anim and self.anim.dice and 0 <= self.anim.current_idx < self.anim.dice.face_count():
            face_col = self.anim.dice.get_face(self.anim.current_idx).bg_color
        act_col = face_col
        tgt_col = (int(0.4*255 + 0.6*(255 - act_col[0])),
                   int(0.4*255 + 0.6*(255 - act_col[1])),
                   int(0.4*255 + 0.6*(255 - act_col[2])))

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
        sh_rect.centerx = self.surface.get_rect().centerx
        sh_rect.top = 18 + 2

        # Panel
        pygame.draw.rect(hdr, color, hdr.get_rect(), border_radius=14)
        pygame.draw.rect(hdr, (255, 255, 255, 36), hdr.get_rect(), width=2, border_radius=14)

        # Title row
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
        # arrow from Actor to Target
        p0 = (act_x + act_chip.get_width() + 6, chips_y + act_chip.get_height() // 2)
        p1 = (tgt_x - 6,                      chips_y + tgt_chip.get_height() // 2)
        self._draw_arrow(hdr, p0, p1)

        # Store
        rect = hdr.get_rect()
        rect.centerx = self.surface.get_rect().centerx
        rect.top = 18

        self._header_surf = hdr
        self._header_rect = rect
        self._header_shadow = shadow
        self._header_shadow_rect = sh_rect
        self._header_dirty = False

    def draw(self):
        if self.state == self.IDLE:
            # Kick queued roll if any (safety: in case you queued without a prior roll)
            if self._pending:
                die, cb, kw = self._pending.pop(0)
                self.start_roll(die, cb, **kw)
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

        # Header
        if self._header_dirty:
            self._rebuild_header()
        if self._header_surf and self._header_rect:
            # subtle shadow for readability
            if hasattr(self, "_header_shadow") and self._header_shadow is not None:
                self.surface.blit(self._header_shadow, self._header_shadow_rect)
            self.surface.blit(self._header_surf, self._header_rect)

        # Close prompt when showing
        if self.state == self.SHOWING and self._prompt_surf:
            prect = self._prompt_surf.get_rect()
            prect.centerx = self.rect.centerx
            prect.top = self.rect.bottom + 18
            self.surface.blit(self._prompt_surf, prect)




# ---------------------- DEMO ----------------------

def demo():
    pygame.init()
    screen = pygame.display.set_mode((960, 540), pygame.RESIZABLE)
    clock = pygame.time.Clock()
    pygame.display.set_caption("Smooth Dice Demo — 1/2 to open dice, click to roll/close")

    die1 = Dice.from_strings([
        "Coup d'État",
        "Proxy War",
        "Biting Sanctions",
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
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                mgr.surface = screen
                mgr.on_resize(event.size)
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
