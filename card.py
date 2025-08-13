import pygame
import random
from dataclasses import dataclass
from typing import Optional, Tuple, Callable

# ---------------------------------------------------------------------------
# Card Draw Manager — V2 with Outcome Styling (ACE scary, KING nice, others NO EFFECT)
# No external assets needed. Procedural visuals tuned for Cold War vibe.
# ---------------------------------------------------------------------------
# API
#   mgr = CardDrawManager(screen)
#   mgr.start_draw(on_result=callback, title="DEFCON DRAW")
#   # in loop: mgr.handle_event(e); mgr.update(dt); mgr.draw()
#
# Typical GameState wrapper
#   def draw_card_defcon(self, aces_delta: int, kings_delta: int):
#       def _on(card):
#           if card.rank == 'A': self.change_defcon(aces_delta)
#           elif card.rank == 'K': self.change_defcon(kings_delta)
#           self.action_log.append(f"Card drawn: {card.rank}{card.suit}")
#       self.card_mgr.start_draw(on_result=_on, title="DEFCON DRAW")
# ---------------------------------------------------------------------------

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A"] + [str(n) for n in range(2, 11)] + ["J", "Q", "K"]
Color = Tuple[int, int, int]

@dataclass
class Card:
    rank: str
    suit: str

class CardDeck:
    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self.cards = [Card(r, s) for s in SUITS for r in RANKS]
        self.shuffle()
    def shuffle(self):
        self.rng.shuffle(self.cards)
    def draw(self) -> Card:
        if not self.cards:
            self.cards = [Card(r, s) for s in SUITS for r in RANKS]
            self.shuffle()
        return self.cards.pop()

class CardDrawAnimation:
    """Flip animation with X-scale squash and slide-in.
    The animation also renders front styling based on outcome (A/K/other).
    """
    def __init__(self, size: Tuple[int, int], flip_ms: int = 650, hold_ms: int = 900, slide_offset_px: int = 160):
        self.size = size
        self.flip_ms = flip_ms
        self.hold_ms = hold_ms
        self.slide_offset_px = slide_offset_px
        self.elapsed = 0
        self.running = False
        self.card: Optional[Card] = None

    def start(self, card: Card):
        self.card = card
        self.elapsed = 0
        self.running = True

    def update(self, dt_ms: int):
        if not self.running:
            return
        self.elapsed += dt_ms
        if self.elapsed >= self.flip_ms + self.hold_ms:
            self.running = False

    def is_done(self) -> bool:
        return not self.running

    def _ease_out_cubic(self, t: float) -> float:
        t = max(0.0, min(1.0, t))
        p = t - 1.0
        return 1.0 + p * p * p

    def _rounded_rect(self, surf: pygame.Surface, rect: pygame.Rect, color: Color, radius: int = 16, width: int = 0):
        pygame.draw.rect(surf, color, rect, width=width, border_radius=radius)

    def _draw_card_back(self, surf: pygame.Surface, rect: pygame.Rect, font_small: pygame.font.Font):
        # Graphite + hatch + small project mark
        self._rounded_rect(surf, rect, (25, 28, 33))
        inner = rect.inflate(-12, -12)
        step = 10
        for i in range(0, inner.width + inner.height, step):
            pygame.draw.line(surf, (50, 55, 62), (inner.left + i, inner.top), (inner.left, inner.top + i), 1)
        emblem = font_small.render("PROJECT ABLE", True, (185, 190, 200))
        surf.blit(emblem, (inner.centerx - emblem.get_width() // 2, inner.centery - emblem.get_height() // 2))

    def _draw_card_front(self, surf: pygame.Surface, rect: pygame.Rect, card: Card,
                          font_big: pygame.font.Font, font_med: pygame.font.Font, font_small: pygame.font.Font):
        # Base manila dossier
        base_col = (222, 209, 173)
        accent_col = (235, 224, 195)
        # Outcome-driven accenting
        if card.rank == 'A':
            # Make it look ominous: darker tint
            base_col = (205, 190, 155)
            accent_col = (225, 210, 175)
        elif card.rank == 'K':
            # Friendlier tint
            base_col = (220, 225, 210)
            accent_col = (236, 240, 228)

        self._rounded_rect(surf, rect, base_col)
        inner = rect.inflate(-14, -14)
        self._rounded_rect(surf, inner, accent_col, radius=12)

        # Outcome stamp
        if card.rank == 'A':
            stamp_text = "ALERT"
            stamp_col = (190, 36, 36)
            angle = -12
        elif card.rank == 'K':
            stamp_text = "DE-ESCALATION"
            stamp_col = (42, 140, 82)
            angle = -10
        else:
            stamp_text = "INCONCLUSIVE"
            stamp_col = (110, 110, 120)
            angle = -14

        stamp = font_med.render(stamp_text, True, stamp_col)
        stamp_surf = pygame.Surface(stamp.get_size(), pygame.SRCALPHA)
        stamp_surf.blit(stamp, (0, 0))
        stamp_surf = pygame.transform.rotozoom(stamp_surf, angle, 1.0)
        surf.blit(stamp_surf, (inner.left + 10, inner.top + 8))

        # Central rank label
        if card.rank == 'A':
            label = "ACE"
        elif card.rank == 'K':
            label = "KING"
        else:
            label = card.rank
        center_text = font_big.render(label, True, (18, 20, 22))
        surf.blit(center_text, (inner.centerx - center_text.get_width() // 2,
                                inner.centery - center_text.get_height() // 2))

        # Suit corners
        suit = card.suit
        suit_col = (180, 30, 30) if suit in ("♥", "♦") else (40, 40, 40)
        tl = font_small.render(f"{card.rank}{suit}", True, suit_col)
        br = font_small.render(f"{card.rank}{suit}", True, suit_col)
        surf.blit(tl, (inner.left + 6, inner.top + 4))
        br_rot = pygame.transform.rotate(br, 180)
        surf.blit(br_rot, (inner.right - br_rot.get_width() - 6, inner.bottom - br_rot.get_height() - 4))

        # Extra outcome flourishes
        if card.rank == 'A':
            # Hazard stripes overlay
            hz = inner.inflate(-10, -10)
            for i in range(0, hz.width + hz.height, 22):
                pygame.draw.line(surf, (150, 30, 30), (hz.left + i, hz.top), (hz.left, hz.top + i), 3)
        elif card.rank == 'K':
            # Subtle star glints
            gl = inner.inflate(-30, -30)
            for _ in range(10):
                x = gl.left + random.randint(0, gl.width)
                y = gl.top + random.randint(0, gl.height)
                pygame.draw.circle(surf, (245, 250, 245), (x, y), 1)

    def draw(self, screen: pygame.Surface, center: Tuple[int, int]):
        w0, h0 = self.size
        card_surf = pygame.Surface((w0, h0), pygame.SRCALPHA)
        rect = card_surf.get_rect()

        font_big = pygame.font.SysFont("Segoe UI", max(28, h0 // 8), bold=True)
        font_med = pygame.font.SysFont("Segoe UI", max(18, h0 // 18), bold=True)
        font_small = pygame.font.SysFont("Segoe UI", max(14, h0 // 22))

        # Flip progress
        t = min(self.elapsed / self.flip_ms, 1.0)
        eased = self._ease_out_cubic(t)
        showing_front = (t >= 0.5)
        slide_t = min(1.0, self.elapsed / (self.flip_ms * 0.6))
        slide = int((1.0 - slide_t) * self.slide_offset_px)

        if not showing_front:
            self._draw_card_back(card_surf, rect, font_small)
        else:
            self._draw_card_front(card_surf, rect, self.card, font_big, font_med, font_small)

        import math
        angle = eased * math.pi
        squash = max(0.06, abs(math.cos(angle)))
        scaled = pygame.transform.smoothscale(card_surf, (max(2, int(w0 * squash)), h0))
        out_rect = scaled.get_rect(center=(center[0], center[1] - slide))
        screen.blit(scaled, out_rect)

class CardDrawManager:
    IDLE = 0
    AWAIT_CLICK = 1
    FLIPPING = 2
    SHOWING = 3

    def __init__(self, surface: pygame.Surface, *, dim_background: bool = True):
        self.surface = surface
        self.dim_background = dim_background
        self._dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 160))

        self.state = self.IDLE
        self.deck = CardDeck()
        self.anim = CardDrawAnimation(self._card_size())
        self.on_result: Optional[Callable[[Card], None]] = None
        self.card: Optional[Card] = None

        # Layout
        self.rect = pygame.Rect(0, 0, *self._card_size())
        self.rect.center = surface.get_rect().center

        # Text elements
        self._font_title = pygame.font.SysFont("Impact", 54)
        self._font_prompt = pygame.font.SysFont("Segoe UI", 26, bold=True)
        self._font_msg = pygame.font.SysFont("Segoe UI", 32, bold=True)
        self._title_surf: Optional[pygame.Surface] = None
        self._title_rect: Optional[pygame.Rect] = None
        self._prompt_surf: Optional[pygame.Surface] = None
        self._prompt_close: Optional[pygame.Surface] = None
        self._effect_msg: Optional[pygame.Surface] = None
        self.title_text = "DRAW A CARD"
        self._build_title()
        self._blink_timer = 0.0  # for ACE blinking

    # --------------- API ---------------
    def start_draw(self, *, on_result: Optional[Callable[[Card], None]] = None, title: Optional[str] = None) -> bool:
        if self.is_active():
            return False
        self.on_result = on_result
        if title:
            self.title_text = title
            self._build_title()
        self._prompt_surf = self._render_prompt("Click to DRAW")
        self._prompt_close = None
        self._effect_msg = None
        self.state = self.AWAIT_CLICK
        self._blink_timer = 0.0
        return True

    def is_active(self) -> bool:
        return self.state != self.IDLE

    # --------- Loop hooks ---------
    def handle_event(self, event: pygame.event.Event):
        if self.state == self.IDLE:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.state == self.AWAIT_CLICK:
                self.card = self.deck.draw()
                self.anim = CardDrawAnimation(self._card_size())
                self.anim.start(self.card)
                self.state = self.FLIPPING
                return
            if self.state == self.SHOWING and self._prompt_close is not None:
                cb = self.on_result
                card = self.card
                # teardown first
                self.state = self.IDLE
                self.card = None
                self.on_result = None
                if cb and card:
                    cb(card)
                return

    def update(self, dt: float):
        if self.state == self.FLIPPING and self.anim:
            self.anim.update(int(dt * 1000))
            if self.anim.is_done():
                # Build outcome messaging and close prompt
                color = (60, 160, 95) if (self.card and self.card.rank == "K") else (
                        (200, 60, 60) if (self.card and self.card.rank == "A") else (120, 125, 135))
                msg_text = self._effect_text(self.card)
                self._effect_msg = self._render_effect_message(msg_text, color)
                self._prompt_close = self._render_prompt("Click to CONTINUE", bg=color)
                self.state = self.SHOWING
        if self.state == self.SHOWING and self.card and self.card.rank == 'A':
            # slow blink for ACE background stripe
            self._blink_timer += dt

    def draw(self):
        if self.state == self.IDLE:
            return
        if self.dim_background:
            # Dim background; intensify on ACE with a pulse
            alpha = 160
            if self.state == self.SHOWING and self.card and self.card.rank == 'A':
                import math
                alpha = 140 + int(40 * (0.5 * (1 + math.sin(self._blink_timer * 6.0))))
            self._dim.fill((0, 0, 0, alpha))
            self.surface.blit(self._dim, (0, 0))

        # Title
        if self._title_surf and self._title_rect:
            self.surface.blit(self._title_surf, self._title_rect)

        center = self.rect.center
        if self.state == self.AWAIT_CLICK:
            if self._prompt_surf:
                rect = self._prompt_surf.get_rect(center=center)
                self.surface.blit(self._prompt_surf, rect)
        elif self.state in (self.FLIPPING, self.SHOWING):
            if self.anim and self.card:
                self.anim.draw(self.surface, center)
            # Outcome message below card
            if self.state == self.SHOWING and self._effect_msg:
                mrect = self._effect_msg.get_rect()
                mrect.centerx = center[0]
                mrect.top = self.rect.bottom + 16
                self.surface.blit(self._effect_msg, mrect)
            # Close prompt
            if self.state == self.SHOWING and self._prompt_close:
                prect = self._prompt_close.get_rect()
                prect.centerx = center[0]
                prect.top = (self.rect.bottom + 16) + (self._effect_msg.get_height() + 12 if self._effect_msg else 0)
                self.surface.blit(self._prompt_close, prect)

    # --------------- Resizing ---------------
    def on_resize(self, size: Tuple[int, int]):
        self._dim = pygame.Surface(size, pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 160))
        self.rect.size = self._card_size()
        self.rect.center = pygame.Rect((0, 0), size).center
        self._build_title()
        if self.state == self.AWAIT_CLICK:
            self._prompt_surf = self._render_prompt("Click to DRAW")

    # --------------- Internals ---------------
    def _card_size(self) -> Tuple[int, int]:
        w, h = self.surface.get_size()
        cw = max(200, int(w * 0.22))
        ch = int(cw * 1.4)
        return cw, ch

    def _render_prompt(self, text: str, bg: Optional[Color] = None) -> pygame.Surface:
        pad_x, pad_y = 16, 10
        ts = self._font_prompt.render(text, True, (20, 20, 25))
        surf = pygame.Surface((ts.get_width() + pad_x * 2, ts.get_height() + pad_y * 2), pygame.SRCALPHA)
        color = bg or (230, 210, 110)
        pygame.draw.rect(surf, color, surf.get_rect(), border_radius=12)
        pygame.draw.rect(surf, (255, 255, 255, 40), surf.get_rect(), 2, border_radius=12)
        surf.blit(ts, (pad_x, pad_y))
        return surf

    def _render_effect_message(self, text: str, color: Color) -> pygame.Surface:
        ts = self._font_msg.render(text, True, (18, 20, 22))
        pad_x, pad_y = 16, 12
        surf = pygame.Surface((ts.get_width() + pad_x * 2, ts.get_height() + pad_y * 2), pygame.SRCALPHA)
        pygame.draw.rect(surf, color, surf.get_rect(), border_radius=12)
        pygame.draw.rect(surf, (255, 255, 255, 40), surf.get_rect(), 2, border_radius=12)
        surf.blit(ts, (pad_x, pad_y))
        return surf

    def _effect_text(self, card: Optional[Card]) -> str:
        if not card:
            return "NO EFFECT"
        if card.rank == 'A':
            return "ACE drawn — DEFCON Lowered"
        if card.rank == 'K':
            return "KING drawn — DEFCON Raised"
        return "No effect"

    def _build_title(self):
        txt = self.title_text
        ts = self._font_title.render(txt, True, (235, 235, 240))
        shadow = self._font_title.render(txt, True, (20, 20, 26))
        surf = pygame.Surface((ts.get_width() + 18, ts.get_height() + 20), pygame.SRCALPHA)
        surf.blit(shadow, (9 + 2, 9 + 2))
        surf.blit(ts, (9, 9))
        self._title_surf = surf
        rect = surf.get_rect()
        rect.centerx = self.surface.get_rect().centerx
        rect.top = 12
        self._title_rect = rect

# ---------------------- Demo ----------------------

def _demo():
    pygame.init()
    screen = pygame.display.set_mode((960, 540), pygame.RESIZABLE)
    clock = pygame.time.Clock()
    pygame.display.set_caption("Card Draw Manager V2 Demo — press D to open; click to draw/continue")

    mgr = CardDrawManager(screen)

    def on_card(card: Card):
        print(f"DREW: {card.rank}{card.suit}")

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_d:
                    mgr.start_draw(on_result=on_card, title="DEFCON DRAW")
            elif e.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((e.w, e.h), pygame.RESIZABLE)
                mgr.surface = screen
                mgr.on_resize((e.w, e.h))
            mgr.handle_event(e)
        mgr.update(dt)

        screen.fill((18, 22, 30))
        info_font = pygame.font.SysFont("Segoe UI", 18)
        tip = info_font.render("Press D to open. Ace = scary (DEFCON -1), King = nice (DEFCON +1), others = No effect.", True, (210, 214, 220))
        screen.blit(tip, (16, 76))

        mgr.draw()
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    _demo()
