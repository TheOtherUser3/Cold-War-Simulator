import pygame
from typing import Optional, Callable, Tuple, Literal

Color = Tuple[int, int, int]
Mode = Literal["discount_next_tier", "fixed_purchase_to_tier"]

class OfferManager:
    """
    General YES/NO modal for Arms/Space offers (USA or USSR) with subject-aware badges.

    Badges:
      - space_race  -> left STAR, right CRESCENT
      - arms_race   -> left SHIELD (smaller), right RANK CHEVRONS (smaller)

    Modes:
      1) "discount_next_tier": buy the next tier at a discount
      2) "fixed_purchase_to_tier": pay a fixed price to jump to a target tier

    Returns the user's choice and price via on_result(accepted: bool, price_paid: int).
    """

    IDLE = 0
    ASKING = 1
    RESULT = 2

    DEFAULT_COSTS = {
        "arms_race": [300, 900, 1600, 2000],
        "space_race": [300, 900, 1600, 2000],
    }

    def __init__(self, surface: pygame.Surface, *, show_badges: bool = True):
        self.surface = surface
        self.show_badges = show_badges
        self.state = self.IDLE

        # Colors — Cold War palette
        self.overlay_alpha = 170
        self.col_bg_panel: Color = (236, 232, 224)
        self.col_border: Color = (32, 28, 28)
        self.col_header: Color = (128, 16, 16)
        self.col_header_light: Color = (200, 40, 40)
        self.col_text_main: Color = (24, 22, 22)
        self.col_yes: Color = (46, 120, 72)
        self.col_no: Color = (160, 48, 48)
        self.col_disabled: Color = (170, 168, 164)

        # Fonts
        self.font_title = self._pick_font(["Impact", "Stencil", "Agency FB", "Arial Black"], 56)
        self.font_body = pygame.font.SysFont("Segoe UI", 26)
        self.font_btn = pygame.font.SysFont("Segoe UI", 28, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI", 22, bold=True)

        # Overlay
        self._overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, self.overlay_alpha))

        # Layout rects
        self.panel_rect = pygame.Rect(0, 0, 820, 420)
        self.header_rect = pygame.Rect(0, 0, 820, 86)
        self.body_rect = pygame.Rect(0, 0, 820, 334)
        self.btn_yes_rect = pygame.Rect(0, 0, 280, 64)
        self.btn_no_rect = pygame.Rect(0, 0, 280, 64)

        # Runtime
        self._actor: Optional[object] = None
        self._subject: str = "arms_race"  # or "space_race"
        self._mode: Mode = "discount_next_tier"
        self._discount: float = 0.5
        self._target_tier: Optional[int] = None
        self._price: int = 0
        self._base_cost: int = 0
        self._can_afford: bool = False
        self._at_max: bool = False
        self._title_text: Optional[str] = None
        self._question_text: Optional[str] = None
        self.on_result: Optional[Callable[[bool, int], None]] = None
        self._accepted: Optional[bool] = None

        self.on_resize(self.surface.get_size())

    # ---------- Public API ----------
    def start_offer(
        self,
        actor: object,
        *,
        subject: Literal["arms_race", "space_race"],
        mode: Mode,
        discount: Optional[float] = None,
        price: Optional[int] = None,
        target_tier: Optional[int] = None,
        title: Optional[str] = None,
        question: Optional[str] = None,
        costs_override: Optional[list] = None,
        on_result: Optional[Callable[[bool, int], None]] = None,
    ) -> bool:
        if self.state != self.IDLE:
            return False

        self._actor = actor
        self._subject = subject
        self._mode = mode
        self._discount = float(discount) if discount is not None else 0.5
        self._target_tier = int(target_tier) if target_tier is not None else None
        self._title_text = title
        self._question_text = question
        self.on_result = on_result
        self._accepted = None

        tier_attr = subject
        current_tier = int(getattr(actor, tier_attr, 0) or 0)
        max_tier = 4
        costs = (costs_override or self.DEFAULT_COSTS.get(subject) or self.DEFAULT_COSTS["arms_race"])  # safe fallback

        if self._mode == "discount_next_tier":
            if current_tier >= max_tier:
                self._at_max = True; self._base_cost = 0; self._price = 0
            else:
                self._at_max = False
                self._base_cost = costs[current_tier]
                self._price = int(self._base_cost * self._discount + 0.999)
        else:  # fixed_purchase_to_tier
            tgt = self._target_tier if self._target_tier is not None else current_tier + 1
            tgt = max(0, min(max_tier, tgt))
            if price is None:
                idx = min(current_tier, max_tier - 1)
                self._base_cost = costs[idx]
                self._price = int(self._base_cost)
            else:
                self._base_cost = int(price)
                self._price = self._base_cost
            self._at_max = current_tier >= tgt

        self._can_afford = (getattr(actor, "pp", 0) >= self._price) and (not self._at_max)
        self.state = self.ASKING
        return True

    def is_active(self) -> bool:
        return self.state != self.IDLE

    def handle_event(self, event: pygame.event.Event):
        if self.state == self.IDLE:
            return
        if event.type == pygame.VIDEORESIZE:
            self.surface = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            self.on_resize(event.size); return
        if self.state == self.ASKING:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if self.btn_yes_rect.collidepoint(mx, my):
                    if self._can_afford: self._choose(True)
                    return
                if self.btn_no_rect.collidepoint(mx, my):
                    self._choose(False); return
        if self.state == self.RESULT:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cb = self.on_result
                accepted = bool(self._accepted)
                price = int(self._price) if accepted else 0
                self.state = self.IDLE
                self._actor = None
                self.on_result = None
                self._accepted = None
                if cb: cb(accepted, price)

    def update(self, dt: float):
        pass

    def draw(self):
        if self.state == self.IDLE:
            return
        self.surface.blit(self._overlay, (0, 0))

        # Panel
        pygame.draw.rect(self.surface, self.col_bg_panel, self.panel_rect, border_radius=16)
        pygame.draw.rect(self.surface, self.col_border, self.panel_rect, 3, border_radius=16)

        # Header
        pygame.draw.rect(self.surface, self.col_header, self.header_rect, border_radius=16)
        top_h = pygame.Rect(self.header_rect.x + 6, self.header_rect.y + 6, self.header_rect.w - 12, 10)
        pygame.draw.rect(self.surface, self.col_header_light, top_h, border_radius=8)
        hdr = self._title_text or ("ARMS RACE OFFER" if self._subject == "arms_race" else "SPACE RACE OFFER")
        title = self.font_title.render(hdr, True, (242, 240, 236))
        shadow = self.font_title.render(hdr, True, (10, 10, 10))
        trect = title.get_rect(); trect.center = (self.header_rect.centerx, self.header_rect.centery + 4)
        srect = trect.copy(); srect.x += 2; srect.y += 2
        self.surface.blit(shadow, srect); self.surface.blit(title, trect)

        # Body
        pad = 24
        body_area = self.body_rect.inflate(-pad*2, -pad*2)
        y = body_area.y

        if self.show_badges:
            left_badge, right_badge = self._subject_badges((200, 60))
            lb_rect = left_badge.get_rect(); rb_rect = right_badge.get_rect()
            lb_rect.topleft = (body_area.x, y)
            rb_rect.topright = (body_area.right, y)
            self.surface.blit(left_badge, lb_rect); self.surface.blit(right_badge, rb_rect)
            y += lb_rect.h + 8

        # Text
        actor_name = getattr(self._actor, "name", "Unknown") if self._actor else ""
        is_arms = (self._subject == "arms_race")
        q_default = f"{actor_name}: discounted {'Arms' if is_arms else 'Space'} Race tier?"
        q = self._question_text or q_default

        if self._mode == "discount_next_tier":
            discount_pct = int(self._discount * 100)
            detail = f"Discount: {discount_pct}%  |  Tier cost: {self._base_cost}  |  Price now: {self._price}"
        else:
            detail = f"Price: {self._price}"

        line3 = "Already at required tier." if self._at_max else (
            ("Insufficient PP." if not self._can_afford else f"PP after purchase: {getattr(self._actor, 'pp', 0) - self._price}")
        )

        for ln in (q, detail, line3):
            ts = self.font_body.render(ln, True, self.col_text_main)
            self.surface.blit(ts, (body_area.x, y)); y += ts.get_height() + 6

        # Buttons
        btn_gap = 30
        btn_y = self.body_rect.bottom - pad - self.btn_yes_rect.h
        total_w = self.btn_yes_rect.w + self.btn_no_rect.w + btn_gap
        start_x = self.body_rect.centerx - total_w // 2
        self.btn_yes_rect.topleft = (start_x, btn_y)
        self.btn_no_rect.topleft = (start_x + self.btn_yes_rect.w + btn_gap, btn_y)
        yes_col = self.col_yes if self._can_afford else self.col_disabled
        self._draw_button(self.btn_yes_rect, "YES", yes_col, enabled=self._can_afford)
        self._draw_button(self.btn_no_rect, "NO", self.col_no, enabled=True)

        # Result chip
        if self.state == self.RESULT and self._accepted is not None:
            txt = "Purchased!" if self._accepted else "Declined"
            col = self.col_yes if self._accepted else self.col_no
            res = self.font_btn.render(txt, True, (245, 245, 245))
            res_bg = pygame.Surface((res.get_width() + 24, res.get_height() + 12))
            res_bg.fill(col)
            res_rect = res_bg.get_rect(); res_rect.centerx = self.panel_rect.centerx; res_rect.top = self.btn_yes_rect.top - 56
            self.surface.blit(res_bg, res_rect); self.surface.blit(res, (res_rect.x + 12, res_rect.y + 6))

    # ---------- Internals ----------
    def _choose(self, yes: bool):
        if self.state != self.ASKING: return
        if yes and not self._can_afford: return
        self._accepted = bool(yes); self.state = self.RESULT

    def _badge_frame(self, size: Tuple[int, int]) -> pygame.Surface:
        w, h = size
        s = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(s, (245, 243, 239), (0, 0, w, h), border_radius=8)
        pygame.draw.rect(s, (90, 80, 70), (0, 0, w, h), 2, border_radius=8)
        return s

    # --- Space badges (unchanged size) ---
    def _badge_star(self, size: Tuple[int, int]) -> pygame.Surface:
        s = self._badge_frame(size)
        w, h = s.get_size(); cx, cy = w//2, h//2
        R, r = min(w, h)//3, min(w, h)//6
        pts = []
        import math
        for i in range(10):
            ang = -math.pi/2 + i * (math.pi/5)
            radius = R if i % 2 == 0 else r
            pts.append((cx + int(radius*math.cos(ang)), cy + int(radius*math.sin(ang))))
        pygame.draw.polygon(s, (70, 70, 70), pts)
        return s

    def _badge_crescent(self, size: Tuple[int, int]) -> pygame.Surface:
        s = self._badge_frame(size)
        w, h = s.get_size(); cx, cy = w//2, h//2
        R = min(w, h)//3
        pygame.draw.circle(s, (70, 70, 70), (cx, cy), R)
        pygame.draw.circle(s, self.col_bg_panel, (cx + R//3, cy), R)
        return s

    # --- Arms badges (scaled smaller to stay inside the frame) ---
    def _inner_rect(self, surf: pygame.Surface, pad_x: int, pad_y: int) -> pygame.Rect:
        r = surf.get_rect()
        r = r.inflate(-pad_x*2, -pad_y*2)
        return r

    def _badge_shield(self, size: Tuple[int, int]) -> pygame.Surface:
        """Smaller heraldic shield: kept inside an inner rect so it never touches/breaches the frame."""
        s = self._badge_frame(size)
        inner = self._inner_rect(s, pad_x=28, pad_y=12)  # <- tighter padding than before
        cx = inner.centerx
        top, bottom = inner.top, inner.bottom
        left, right = inner.left, inner.right
        pts = [
            (left + 8, top + 10),
            (cx, top + 2),
            (right - 8, top + 10),
            (right - 6, (top + bottom)//2),
            (cx, bottom - 4),
            (left + 6, (top + bottom)//2),
        ]
        pygame.draw.polygon(s, (70, 70, 70), pts)
        # inner stripe
        stripe = pygame.Rect(cx - 6, top + 10, 12, bottom - top - 20)
        pygame.draw.rect(s, (110, 110, 110), stripe, border_radius=4)
        return s

    def _badge_chevrons(self, size: Tuple[int, int]) -> pygame.Surface:
        """Three smaller rank chevrons stacked; thickness and margins reduced."""
        s = self._badge_frame(size)
        inner = self._inner_rect(s, pad_x=28, pad_y=12)
        w, h = inner.size
        cx = inner.centerx
        margin = 10
        thickness = 6
        gap = 5
        rise = 12
        base_y = inner.bottom - margin + 8
        color = (70, 70, 70)
        for i in range(3):
            y = base_y - i * (thickness + gap)
            left = (inner.left + margin, y)
            mid = (cx, y - rise)
            right = (inner.right - margin, y)
            pygame.draw.lines(s, color, False, [left, mid, right], thickness)
        return s

    def _subject_badges(self, size: Tuple[int, int]):
        if self._subject == "space_race":
            return self._badge_star(size), self._badge_crescent(size)
        else:  # arms_race (smaller symbols)
            return self._badge_shield(size), self._badge_chevrons(size)

    def _draw_button(self, rect: pygame.Rect, label: str, bg: Color, *, enabled: bool = True):
        pygame.draw.rect(self.surface, bg, rect, border_radius=10)
        pygame.draw.rect(self.surface, self.col_border, rect, 2, border_radius=10)
        txt = self.font_btn.render(label, True, (245, 245, 245) if enabled else (220, 220, 220))
        trect = txt.get_rect(); trect.center = rect.center
        self.surface.blit(txt, trect)
        if not enabled:
            hatch = pygame.Surface(rect.size, pygame.SRCALPHA)
            for x in range(0, rect.w, 10):
                pygame.draw.line(hatch, (0, 0, 0, 35), (x, 0), (x + 16, rect.h), 3)
            self.surface.blit(hatch, rect)

    def on_resize(self, size: Tuple[int, int]):
        sw, sh = size
        self._overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, self.overlay_alpha))
        self.panel_rect.size = (min(860, int(sw * 0.78)), min(460, int(sh * 0.60)))
        self.panel_rect.center = (sw // 2, sh // 2)
        self.header_rect.size = (self.panel_rect.w, 86); self.header_rect.topleft = self.panel_rect.topleft
        self.body_rect.size = (self.panel_rect.w, self.panel_rect.h - self.header_rect.h)
        self.body_rect.topleft = (self.panel_rect.x, self.header_rect.bottom)
        bw = max(240, min(320, self.panel_rect.w // 3))
        self.btn_yes_rect.size = (bw, 64); self.btn_no_rect.size = (bw, 64)

    @staticmethod
    def _pick_font(candidates, size, *, bold=False):
        for name in candidates:
            try:
                return pygame.font.SysFont(name, size, bold=bold)
            except Exception:
                continue
        return pygame.font.SysFont(None, size, bold=bold)


# --------------------------- DEMO ---------------------------
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((1100, 700), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    class _Country:
        def __init__(self, name: str, pp: int, arms_race: int = 0, space_race: int = 0):
            self.name = name; self.pp = pp; self.arms_race = arms_race; self.space_race = space_race

    usa = _Country("USA", pp=350, arms_race=0)
    ussr = _Country("USSR", pp=450, space_race=1)

    mgr = OfferManager(screen)

    def start_space_offer():
        mgr.start_offer(
            ussr,
            subject="space_race",
            mode="fixed_purchase_to_tier",
            price=600,
            target_tier=3,
            title="SPACE RACE OFFER",
            question="USSR: Spend 600 PP now to jump directly to Space Race Tier 3?",
            on_result=lambda ok, price: (
                setattr(ussr, "pp", ussr.pp - price) or setattr(ussr, "space_race", max(ussr.space_race, 3))
            ) if ok else None,
        )

    # Start with a USA arms offer, then chain to USSR space offer for testing badges
    mgr.start_offer(
        usa,
        subject="arms_race",
        mode="discount_next_tier",
        discount=0.5,
        on_result=lambda ok, price: (
            setattr(usa, "pp", usa.pp - price) or setattr(usa, "arms_race", min(4, usa.arms_race + 1)) or start_space_offer()
        ) if ok else start_space_offer(),
    )

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: running = False
            mgr.handle_event(event)
        screen.fill((32, 38, 52))
        pygame.draw.rect(screen, (38, 46, 62), pygame.Rect(0, 0, screen.get_width(), 70))
        title = pygame.font.SysFont("Segoe UI", 24, bold=True).render("Cold War — Demo (arms badges scaled)", True, (220, 226, 232))
        screen.blit(title, (16, 16))
        mgr.draw(); pygame.display.flip()
    pygame.quit()
