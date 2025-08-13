import pygame
import random
from typing import Callable, Optional, Tuple, Sequence

Color = Tuple[int, int, int]

# --------------------------------------------------
# QUIZ POPUP V3 (Cold War aesthetic, targeted answering)
# --------------------------------------------------
# UI is unchanged from V2. Behavioral upgrades:
# - Only the *target country* may answer interactively when it is the
#   currently playing country and NOT AI.
# - If target is AI (or you force observer auto-answer), the UI shows for
#   everyone, input is disabled, and a random answer is chosen after a
#   short randomized delay. Then the current viewer clicks to dismiss.
# - If target is another human (not the current player), the viewer sees
#   the full UI but *cannot* interact. Use `force_answer(True/False)` from
#   your multiplayer/netcode when the remote player answers; the viewer
#   then clicks to dismiss.
# - Callback still fires only after the popup is dismissed.
# --------------------------------------------------


class QuizManager:
    IDLE = 0
    ASKING = 1
    FEEDBACK = 2

    def __init__(self, surface: pygame.Surface, get_currently_playing: Callable[[], object]):
        """
        Args:
            surface: Pygame surface to draw on.
            get_currently_playing: Callable that returns the Country object
                whose turn it is (must expose at least `.name` and `.is_ai`).
        """
        self.surface = surface
        self.get_currently_playing = get_currently_playing
        self.state = self.IDLE

        # Aesthetic colors (Cold War vibe)
        self.overlay_alpha = 170
        self.col_bg_panel: Color = (236, 232, 224)   # off-white paper
        self.col_border: Color = (32, 28, 28)
        self.col_header: Color = (128, 16, 16)       # deep red
        self.col_header_light: Color = (200, 40, 40)
        self.col_text_main: Color = (24, 22, 22)
        self.col_btn_neutral: Color = (210, 206, 198)
        self.col_btn_text: Color = (24, 24, 24)
        self.col_correct: Color = (60, 160, 95)
        self.col_wrong: Color = (200, 50, 50)

        # Fonts
        self.font_title = self._pick_font(["Impact", "Stencil", "Agency FB", "Arial Black"], 56, bold=False)
        self.font_body = pygame.font.SysFont("Segoe UI", 26)
        self.font_btn = pygame.font.SysFont("Segoe UI", 28, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI", 22, bold=True)
        self.font_effect = pygame.font.SysFont("Segoe UI", 24, bold=True)

        # Overlay
        self._overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, self.overlay_alpha))

        # Layout rects
        self.panel_rect = pygame.Rect(0, 0, 800, 440)
        self.header_rect = pygame.Rect(0, 0, 800, 90)
        self.body_rect = pygame.Rect(0, 0, 800, 350)
        self.btn_yes_rect = pygame.Rect(0, 0, 260, 64)
        self.btn_no_rect = pygame.Rect(0, 0, 260, 64)

        # Data
        self.question: str = ""
        self.correct_is_yes: bool = True
        self.effects_if_correct: str = ""
        self.effects_if_wrong: str = ""
        self.on_result: Optional[Callable[[bool, bool, bool], None]] = None  # (selected_yes, correct_is_yes, is_correct)
        self._selected_yes: Optional[bool] = None
        self._is_correct: Optional[bool] = None

        # Targeting / interactivity
        self._target_country: Optional[object] = None
        self._interactive: bool = False
        self._observer_auto_answer: Optional[bool] = None
        self._ai_delay_range_ms: Tuple[int, int] = (1200, 2600)
        self._auto_timer_ms: int = -1

        # Prompt surf shown *below* panel in FEEDBACK
        self._result_prompt_surf: Optional[pygame.Surface] = None
        self._result_prompt_rect: Optional[pygame.Rect] = None

        self.on_resize(self.surface.get_size())

    # ---------------- Public API ----------------
    def start_quiz(
        self,
        question: str,
        correct_is_yes: bool,
        target_country: object,
        on_result: Optional[Callable[[bool, bool, bool], None]] = None,
        *,
        effects_if_correct: str = "",
        effects_if_wrong: str = "",
        ai_delay_range_ms: Sequence[int] = (1200, 2600),
        observer_auto_answer: Optional[bool] = None,
    ) -> bool:
        """
        Launch the quiz.

        Args:
            question: The question text to display.
            correct_is_yes: Whether YES is the correct answer.
            target_country: Country object that should answer (must have `.is_ai` and `.name`).
            on_result: Callback fired *after dismissal* with (selected_yes, correct_is_yes, is_correct).
            effects_if_correct / effects_if_wrong: Effect description strings to show in FEEDBACK.
            ai_delay_range_ms: (min, max) randomized delay before an AI/observer answer is chosen.
            observer_auto_answer: If True, auto-answer even for non-AI observers; if False, wait for `force_answer()`.
                                   If None, auto-answer only when target_country.is_ai is True.
        Returns:
            False if a quiz is already open; True otherwise.
        """
        if self.state != self.IDLE:
            return False

        self.question = question
        self.correct_is_yes = bool(correct_is_yes)
        self.effects_if_correct = effects_if_correct
        self.effects_if_wrong = effects_if_wrong
        self.on_result = on_result
        self._selected_yes = None
        self._is_correct = None
        self._result_prompt_surf = None
        self._result_prompt_rect = None

        self._target_country = target_country
        self._observer_auto_answer = observer_auto_answer
        self._ai_delay_range_ms = (int(ai_delay_range_ms[0]), int(ai_delay_range_ms[1])) if ai_delay_range_ms else (1200, 2600)
        self._auto_timer_ms = -1

        # Determine interactivity by turn ownership
        current = self.get_currently_playing() if self.get_currently_playing else None
        is_current_player = (current is not None and target_country is current)
        is_ai = bool(getattr(target_country, "is_ai", False))

        # Interactive only if it's *their* turn and they are NOT AI
        self._interactive = (is_current_player and not is_ai)

        # If not interactive: decide whether to auto-answer or wait for an external force_answer
        auto_for_observer = self._observer_auto_answer if self._observer_auto_answer is not None else is_ai
        if not self._interactive and auto_for_observer:
            self._auto_timer_ms = random.randint(self._ai_delay_range_ms[0], self._ai_delay_range_ms[1])
        else:
            self._auto_timer_ms = -1  # wait for force_answer()

        self.state = self.ASKING
        return True

    def is_active(self) -> bool:
        return self.state != self.IDLE

    def force_answer(self, yes: bool) -> bool:
        """Externally force an answer (useful for remote human player)."""
        if self.state != self.ASKING:
            return False
        if self._interactive:
            return False  # local player should click the buttons/keys
        if self._selected_yes is not None:
            return False  # already chosen
        self._choose(bool(yes))
        return True

    # ---------------- Events & Update ----------------
    def handle_event(self, event: pygame.event.Event):
        if self.state == self.IDLE:
            return

        if event.type == pygame.VIDEORESIZE:
            self.surface = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            self.on_resize(event.size)
            return

        if self.state == self.ASKING and self._interactive:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_y, pygame.K_RETURN):
                    self._choose(True); return
                elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                    self._choose(False); return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if self.btn_yes_rect.collidepoint(mx, my):
                    self._choose(True); return
                if self.btn_no_rect.collidepoint(mx, my):
                    self._choose(False); return

        if self.state == self.FEEDBACK:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if self.panel_rect.collidepoint(mx, my) or (self._result_prompt_rect and self._result_prompt_rect.collidepoint(mx, my)):
                    self._finish(); return

    def update(self, dt: float):
        if self.state == self.ASKING and not self._interactive and self._auto_timer_ms >= 0 and self._selected_yes is None:
            self._auto_timer_ms -= int(dt * 1000)
            if self._auto_timer_ms <= 0:
                # Randomly pick True/False, 50/50
                self._choose(bool(random.getrandbits(1)))

    # ---------------- Draw ----------------
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

        title = self.font_title.render("QUIZ TIME", True, (242, 240, 236))
        shadow = self.font_title.render("QUIZ TIME", True, (10, 10, 10))
        trect = title.get_rect(); trect.center = (self.header_rect.centerx, self.header_rect.centery + 4)
        srect = trect.copy(); srect.x += 2; srect.y += 2
        self.surface.blit(shadow, srect)
        self.surface.blit(title, trect)

        # Body text
        pad = 24
        body_area = self.body_rect.inflate(-pad*2, -pad*2)
        lines = self._wrap_text(self.question, self.font_body, body_area.w)
        y = body_area.y
        for ln in lines:
            ts = self.font_body.render(ln, True, self.col_text_main)
            self.surface.blit(ts, (body_area.x, y))
            y += ts.get_height() + 6

        # Buttons
        btn_gap = 30
        btn_y = self.body_rect.bottom - pad - self.btn_yes_rect.h
        total_w = self.btn_yes_rect.w + self.btn_no_rect.w + btn_gap
        start_x = self.body_rect.centerx - total_w // 2
        self.btn_yes_rect.topleft = (start_x, btn_y)
        self.btn_no_rect.topleft = (start_x + self.btn_yes_rect.w + btn_gap, btn_y)

        if self.state == self.ASKING:
            # Hover only when interactive; visuals unchanged otherwise
            self._draw_button(self.btn_yes_rect, "YES", self.col_btn_neutral, hover=self._interactive)
            self._draw_button(self.btn_no_rect, "NO", self.col_btn_neutral, hover=self._interactive)
        elif self.state == self.FEEDBACK:
            sel_yes = bool(self._selected_yes)
            is_corr = bool(self._is_correct)
            yes_col = self._btn_color_for(True, sel_yes, is_corr)
            no_col = self._btn_color_for(False, sel_yes, is_corr)

            self._draw_button(self.btn_yes_rect, "YES", yes_col, hover=False)
            self._draw_button(self.btn_no_rect, "NO", no_col, hover=False)

            # EFFECTS text: show above result chip
            effects_text = self.effects_if_correct if is_corr else self.effects_if_wrong
            if effects_text:
                et_lines = self._wrap_text("Effects: " + effects_text, self.font_effect, body_area.w)
                ey = self.btn_yes_rect.top - 96
                for ln in et_lines:
                    ets = self.font_effect.render(ln, True, self.col_text_main)
                    etr = ets.get_rect(); etr.centerx = self.panel_rect.centerx; etr.top = ey
                    self.surface.blit(ets, etr)
                    ey += ets.get_height() + 4

            # Result chip
            result_txt = "Correct!" if is_corr else "Incorrect"
            col = self.col_correct if is_corr else self.col_wrong
            res = self.font_btn.render(result_txt, True, (245, 245, 245))
            res_bg = pygame.Surface((res.get_width() + 24, res.get_height() + 12))
            res_bg.fill(col)
            res_rect = res_bg.get_rect(); res_rect.centerx = self.panel_rect.centerx; res_rect.top = self.btn_yes_rect.top - 56
            self.surface.blit(res_bg, res_rect)
            self.surface.blit(res, (res_rect.x + 12, res_rect.y + 6))

            # Click-to-continue prompt (below panel)
            if self._result_prompt_surf is None:
                self._result_prompt_surf = self._make_prompt("Click to continue")
                self._result_prompt_rect = self._result_prompt_surf.get_rect(); self._result_prompt_rect.centerx = self.panel_rect.centerx; self._result_prompt_rect.top = self.panel_rect.bottom + 16
            self.surface.blit(self._result_prompt_surf, self._result_prompt_rect)

    # ---------------- Internals ----------------
    def _choose(self, yes: bool):
        if self.state != self.ASKING:
            return
        self._selected_yes = yes
        self._is_correct = (yes == self.correct_is_yes)
        self.state = self.FEEDBACK

    def _finish(self):
        if self.state != self.FEEDBACK:
            return
        cb = self.on_result
        selected_yes = bool(self._selected_yes)
        correct_yes = bool(self.correct_is_yes)
        is_correct = bool(self._is_correct)
        # Reset
        self.state = self.IDLE
        self._selected_yes = None
        self._is_correct = None
        self._result_prompt_surf = None
        self._result_prompt_rect = None
        self._target_country = None
        self._interactive = False
        self._auto_timer_ms = -1
        if cb:
            cb(selected_yes, correct_yes, is_correct)

    def on_resize(self, size: Tuple[int, int]):
        sw, sh = size
        self._overlay = pygame.Surface(size, pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, self.overlay_alpha))

        # Panel scales with window
        pw = min(900, int(sw * 0.85))
        ph = min(540, int(sh * 0.72))
        self.panel_rect.size = (pw, ph)
        self.panel_rect.center = (sw // 2, sh // 2)

        self.header_rect.size = (pw, max(90, int(ph * 0.18)))
        self.header_rect.topleft = self.panel_rect.topleft

        self.body_rect = pygame.Rect(
            self.panel_rect.x, self.panel_rect.y + self.header_rect.h, pw, ph - self.header_rect.h
        )

        # Buttons sized by width
        bw = max(220, min(320, pw // 3))
        bh = 64
        self.btn_yes_rect.size = (bw, bh)
        self.btn_no_rect.size = (bw, bh)

        # Reposition below-panel prompt if present
        if self._result_prompt_surf is not None:
            self._result_prompt_rect = self._result_prompt_surf.get_rect()
            self._result_prompt_rect.centerx = self.panel_rect.centerx
            self._result_prompt_rect.top = self.panel_rect.bottom + 16

    def _draw_button(self, rect: pygame.Rect, text: str, fill: Color, hover: bool):
        mx, my = pygame.mouse.get_pos()
        is_hover = hover and rect.collidepoint(mx, my)
        col = tuple(min(255, c + 16) for c in fill) if is_hover else fill
        pygame.draw.rect(self.surface, col, rect, border_radius=10)
        pygame.draw.rect(self.surface, self.col_border, rect, 2, border_radius=10)
        ts = self.font_btn.render(text, True, self.col_btn_text)
        trect = ts.get_rect(center=rect.center)
        self.surface.blit(ts, trect)

    def _btn_color_for(self, for_yes: bool, selected_yes: bool, is_correct: bool) -> Color:
        if for_yes == selected_yes:
            return self.col_correct if is_correct else self.col_wrong
        return self.col_btn_neutral

    def _make_prompt(self, text: str) -> pygame.Surface:
        pad_x, pad_y = 16, 10
        ts = self.font_small.render(text, True, (20, 20, 25))
        surf = pygame.Surface((ts.get_width() + pad_x * 2, ts.get_height() + pad_y * 2), pygame.SRCALPHA)
        pygame.draw.rect(surf, (230, 210, 110), surf.get_rect(), border_radius=10)
        pygame.draw.rect(surf, (255, 255, 255, 40), surf.get_rect(), 2, border_radius=10)
        surf.blit(ts, (pad_x, pad_y))
        return surf

    def _wrap_text(self, text: str, font: pygame.font.Font, max_width: int):
        words = text.split()
        if not words:
            return [""]
        lines = []
        cur = words[0]
        for w in words[1:]:
            if font.size(cur + " " + w)[0] <= max_width:
                cur += " " + w
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines

    @staticmethod
    def _pick_font(candidates, size, *, bold=False):
        for name in candidates:
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
                _ = f.render("test", True, (255, 255, 255))
                return f
            except Exception:
                continue
        return pygame.font.SysFont(None, size, bold=bold)


# ---------------- Optional demo ----------------
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((1000, 660), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    class DummyCountry:
        def __init__(self, name, is_ai):
            self.name = name
            self.is_ai = is_ai

    # rotate current player among three for demonstration
    players = [DummyCountry("USA", True), DummyCountry("USSR", True), DummyCountry("UK", False)]
    cur_idx = 0

    def get_current():
        return players[cur_idx]

    mgr = QuizManager(screen, get_current)

    def on_quiz_result(selected_yes: bool, correct_yes: bool, is_correct: bool):
        print(f"QUIZ RESULT → selected_yes={selected_yes} correct_yes={correct_yes} is_correct={is_correct}")

    running = True
    pending_force = False
    target = players[1]  # USSR

    while running:
        dt = clock.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_TAB:
                    cur_idx = (cur_idx + 1) % len(players)
                    print("Current:", players[cur_idx].name)
                elif e.key == pygame.K_q and not mgr.is_active():
                    mgr.start_quiz(
                        "Detente raised DEFCON by 3?",
                        correct_is_yes=False,
                        target_country=target,
                        on_result=on_quiz_result,
                        effects_if_correct="DEFCON remains unchanged.",
                        effects_if_wrong="DEFCON raises by three levels.",
                        observer_auto_answer=None,
                    )
                    pending_force = True
                elif e.key == pygame.K_f and mgr.is_active():
                    mgr.force_answer(True)  # simulate remote answer
            mgr.handle_event(e)

        mgr.update(dt)
        screen.fill((18, 18, 26))
        mgr.draw()
        pygame.display.flip()

    pygame.quit()
