import pygame, random, math
from typing import Optional, Callable, Tuple, List, Dict

Color = Tuple[int, int, int]

class BlocMemberVoteManager:
    """
    Modal UI: bloc votes to select which member defects (e.g., Warsaw -> Non‑Aligned).

    This variant adds a **dramatic EJECTION popup** shown *after* the vote resolves and
    you click to continue. Flow:
      1) Vote runs (as before).
      2) When all AI have voted and the human confirms, we show a small "Result" panel that
         says who won and prompts: "Click to continue".
      3) On click, a full‑screen **EJECTION** popup appears with big type: "{COUNTRY} WAS EJECTED".
      4) Click again (or press ESC) to dismiss; callback fires and manager resets.

    Public API remains the same; just import this file instead of your previous manager.
    """

    IDLE   = 0
    ASKING = 1
    RESULT = 2      # compact result panel (click to continue)
    EJECT  = 3      # full‑screen dramatic popup (click to dismiss)

    def __init__(self, surface: pygame.Surface, *, get_bloc_members: Optional[Callable[[str], List[object]]] = None):
        self.surface = surface
        self.get_bloc_members = get_bloc_members
        self.state = self.IDLE
        

        # Colors
        self.overlay_alpha = 170
        self.col_bg_panel: Color = (236, 232, 224)
        self.col_border: Color = (32, 28, 28)
        self.col_header: Color = (128, 16, 16)
        self.col_header_light: Color = (200, 40, 40)
        self.col_text: Color = (24, 22, 22)
        self.col_muted: Color = (88, 86, 82)
        self.col_list_item: Color = (225, 222, 214)
        self.col_list_hover: Color = (246, 244, 238)
        self.col_list_shadow: Color = (190, 186, 178)
        self.col_btn_ok: Color = (46, 120, 72)
        self.col_btn_disabled: Color = (170, 168, 164)
        self.col_scroll_track: Color = (205, 202, 196)
        self.col_scroll_knob: Color = (120, 118, 112)
        self.col_bar_bg: Color = (214, 210, 204)
        self.col_bar_pp: Color = (70, 90, 140)
        self.col_bar_war: Color = (140, 70, 70)
        self.col_bar_arms: Color = (90, 120, 80)
        self.col_bar_space: Color = (110, 90, 140)

        # Fonts
        self.font_title = pygame.font.SysFont("Impact,Stencil,Arial Black", 52)
        self.font_body = pygame.font.SysFont("Segoe UI", 26)
        self.font_small = pygame.font.SysFont("Segoe UI", 18)
        self.font_bold  = pygame.font.SysFont("Segoe UI", 20, bold=True)
        self.font_mono  = pygame.font.SysFont("Consolas,Menlo,DejaVu Sans Mono,monospace", 16)
        self.font_big   = pygame.font.SysFont("Impact,Stencil,Arial Black", 92)
        self.font_big_shadow = pygame.font.SysFont("Impact,Stencil,Arial Black", 92)

        # Overlay
        self._overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, self.overlay_alpha))

        # Layout
        self.panel_rect = pygame.Rect(0, 0, 1040, 660)
        self.header_rect = pygame.Rect(0, 0, 1040, 104)
        self.body_rect   = pygame.Rect(0, 0, 1040, 556)

        # Columns
        self._item_rects: List[Tuple[pygame.Rect, str]] = []
        self.list_rect   = pygame.Rect(0, 0, 620, 400)
        self.detail_rect = pygame.Rect(0, 0, 620, 120)
        self.voters_rect = pygame.Rect(0, 0, 380, 400)
        self.btn_confirm_rect = pygame.Rect(0, 0, 300, 60)

        # Right column sub-areas (scrollable)
        self.voters_list_rect = pygame.Rect(0, 0, 0, 0)
        self.tally_list_rect  = pygame.Rect(0, 0, 0, 0)
        self._voters_scroll_y = 0
        self._tally_scroll_y  = 0
        self._voters_content_h = 0
        self._tally_content_h  = 0

        # Left list scroll state
        self._scroll_y = 0
        self._content_h = 0

        # Runtime
        self._bloc_name: Optional[str] = None
        self._voters: List[object] = []
        self._eligible: List[object] = []
        self._human: Optional[object] = None
        self._title: str = "BLOC MEMBER VOTE"
        self._subtitle: str = "Choose a member to defect"
        self._on_result: Optional[Callable[[object, Dict[str,int], List[Tuple[str,str]]], None]] = None
        self._desc_fn: Optional[Callable[[object], str]] = None
        self._weight_fn: Optional[Callable[[object], float]] = None
        self._ai_delay_ms: Tuple[int,int] = (9000, 18000)

        # Choice bookkeeping
        self._human_choice: Optional[str] = None
        self._human_confirmed: bool = False
        self._ai_due: Dict[str, int] = {}
        self._ai_choice: Dict[str, Optional[str]] = {}
        self._tally: Dict[str, int] = {}
        self._order: List[Tuple[str, str]] = []

        # Ejection result bookkeeping
        self._result_chosen = None
        self._result_tally: Dict[str,int] | None = None
        self._result_order: List[Tuple[str,str]] | None = None
        self._eject_start_ms: Optional[int] = None
        self._eject_name: Optional[str] = None

        # Stat normalization
        self._pp_max = 1
        self._war_max = 1

        self.on_resize(self.surface.get_size())

    # ----------------------- Public API -----------------------
    def start_vote_for_bloc(self, *, bloc_name: str, human_country: object,
                             eligible_names: Optional[List[str]] = None,
                             on_result: Optional[Callable[[object, Dict[str, int], List[Tuple[str, str]]], None]] = None,
                             title: Optional[str] = None, subtitle: Optional[str] = None,
                             desc_fn: Optional[Callable[[object], str]] = None,
                             weight_fn: Optional[Callable[[object], float]] = None,
                             ai_delay_range_ms: Tuple[int, int] = (9000, 18000)) -> bool:
        if self.get_bloc_members is None:
            raise RuntimeError("BlocMemberVoteManager requires get_bloc_members callback for start_vote_for_bloc().")
        members = list(self.get_bloc_members(bloc_name))
        if not members:
            return False
        voters = members
        if eligible_names is None:
            eligible = [m for m in members if m.name != "USSR"]
        else:
            name_set = set(eligible_names)
            eligible = [m for m in members if m.name in name_set]
        return self.start_vote(
            voters=voters, eligible=eligible, human_country=human_country,
            on_result=on_result, title=title or f"{bloc_name} -> Non-Aligned",
            subtitle=subtitle or "Select the member that defects",
            desc_fn=desc_fn, weight_fn=weight_fn,
            ai_delay_range_ms=ai_delay_range_ms, bloc_name=bloc_name)

    def start_vote(self, *, voters: List[object], eligible: List[object], human_country: object,
                   on_result: Optional[Callable[[object, Dict[str, int], List[Tuple[str, str]]], None]] = None,
                   title: Optional[str] = None, subtitle: Optional[str] = None,
                   desc_fn: Optional[Callable[[object], str]] = None,
                   weight_fn: Optional[Callable[[object], float]] = None,
                   ai_delay_range_ms: Tuple[int, int] = (9000, 18000),
                   bloc_name: Optional[str] = None) -> bool:
        if self.state != self.IDLE: return False
        if not voters or not eligible: return False
        self._bloc_name = bloc_name
        self._voters = list(voters)
        self._eligible = list(eligible)
        self._human = human_country
        self._on_result = on_result
        self._title = title or "BLOC MEMBER VOTE"
        self._subtitle = subtitle or "Choose a member to defect"
        self._desc_fn = desc_fn
        self._weight_fn = weight_fn
        self._ai_delay_ms = ai_delay_range_ms
        self._human_choice = None; self._human_confirmed = False
        self._tally = {e.name: 0 for e in self._eligible}
        self._order = []
        self._pp_max = max(1, max(getattr(e, 'pp', 1) for e in self._eligible))
        self._war_max = max(1, max(getattr(e, 'war_power', 1) for e in self._eligible))
        now = pygame.time.get_ticks(); self._ai_due = {}; self._ai_choice = {}
        for v in self._voters:
            if v is self._human or not getattr(v, 'is_ai', False):
                continue
            delay = random.randint(self._ai_delay_ms[0], self._ai_delay_ms[1])
            self._ai_due[v.name] = now + delay; self._ai_choice[v.name] = None
        self._rebuild_item_rects(); self._scroll_y = 0; self._recompute_content_height()
        self._voters_scroll_y = 0; self._tally_scroll_y = 0
        self._result_chosen = None; self._result_tally = None; self._result_order = None
        self._eject_start_ms = None; self._eject_name = None
        self.state = self.ASKING; return True

    def is_active(self) -> bool: return self.state != self.IDLE

    def handle_event(self, event: pygame.event.Event):
        if self.state == self.IDLE: return
        if event.type == pygame.VIDEORESIZE:
            self.surface = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            self.on_resize(event.size); self._rebuild_item_rects(); self._recompute_content_height(); return
        if self.state == self.ASKING:
            if event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if self.list_rect.collidepoint(mx, my):
                    self._scroll_y -= event.y * 48; self._clamp_left_scroll(); return
                if self.voters_list_rect.collidepoint(mx, my):
                    self._voters_scroll_y -= event.y * 40; self._clamp_voters_scroll(); return
                if self.tally_list_rect.collidepoint(mx, my):
                    self._tally_scroll_y -= event.y * 40; self._clamp_tally_scroll(); return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if self.list_rect.collidepoint(mx, my):
                    y0 = 12 - self._scroll_y
                    for r, name in self._item_rects:
                        rdraw = pygame.Rect(self.list_rect.x + 12, self.list_rect.y + y0, r.w, r.h)
                        if rdraw.collidepoint(mx, my): self._human_choice = name; break
                        y0 += r.h + 14
                if self.btn_confirm_rect.collidepoint(mx, my) and self._human_choice is not None:
                    self._human_confirmed = True; self._try_finish()
        elif self.state == self.RESULT:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Promote to EJECTION popup
                self._start_ejection_popup()
        elif self.state == self.EJECT:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._finalize_and_callback()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._finalize_and_callback()

    def update(self, dt: float):
        if self.state != self.ASKING: return
        now = pygame.time.get_ticks()
        for voter_name, due in list(self._ai_due.items()):
            if now >= due and self._ai_choice.get(voter_name) is None:
                choice = self._weighted_choice(); self._ai_choice[voter_name] = choice
                self._tally[choice] += 1; self._order.append((voter_name, choice))
                del self._ai_due[voter_name]
        if self._human_confirmed: self._try_finish()

    def draw(self):
        if self.state == self.IDLE: return
        if self.state in (self.ASKING, self.RESULT):
            self._draw_main_panel()
            if self.state == self.RESULT:
                self._draw_result_overlay()
        elif self.state == self.EJECT:
            self._draw_ejection_popup()

    # ----------------------- Drawing helpers -----------------------
    def _draw_main_panel(self):
        self.surface.blit(self._overlay, (0, 0))
        pygame.draw.rect(self.surface, self.col_bg_panel, self.panel_rect, border_radius=16)
        pygame.draw.rect(self.surface, self.col_border, self.panel_rect, 3, border_radius=16)
        pygame.draw.rect(self.surface, self.col_header, self.header_rect, border_radius=16)
        top_h = pygame.Rect(self.header_rect.x + 6, self.header_rect.y + 6, self.header_rect.w - 12, 10)
        pygame.draw.rect(self.surface, self.col_header_light, top_h, border_radius=8)
        title = self.font_title.render(self._title, True, (242, 240, 236))
        trect = title.get_rect(); trect.center = (self.header_rect.centerx, self.header_rect.centery + 4)
        self.surface.blit(title, trect)
        sub = self.font_bold.render(self._subtitle, True, (235, 232, 228))
        srect = sub.get_rect(); srect.centerx = self.header_rect.centerx; srect.top = self.header_rect.bottom - 28
        self.surface.blit(sub, srect)

        # Left list with clipping
        clip_prev = self.surface.get_clip(); self.surface.set_clip(self.list_rect)
        pygame.draw.rect(self.surface, (248,246,242), self.list_rect, border_radius=10)
        y = self.list_rect.y + 12 - self._scroll_y
        mx, my = pygame.mouse.get_pos(); hover_name = None
        for r, name in self._item_rects:
            rdraw = pygame.Rect(self.list_rect.x + 12, y, r.w, r.h)
            if rdraw.bottom < self.list_rect.top: y += r.h + 14; continue
            if rdraw.top > self.list_rect.bottom: break
            hovered = rdraw.collidepoint(mx, my)
            # shadow
            shadow = rdraw.copy(); shadow.x += 2; shadow.y += 2
            pygame.draw.rect(self.surface, self.col_list_shadow, shadow, border_radius=10)
            bg = self.col_list_hover if hovered else self.col_list_item
            pygame.draw.rect(self.surface, bg, rdraw, border_radius=10)
            pygame.draw.rect(self.surface, (180,176,168), rdraw, 1, border_radius=10)
            # name
            nm = self.font_body.render(name, True, self.col_text)
            self.surface.blit(nm, (rdraw.x + 14, rdraw.y + 12))
            # stats
            c = self._country_by_name(name)
            self._draw_stat_rows(rdraw, c)
            # selection indicator
            if self._human_choice == name:
                pygame.draw.circle(self.surface, (40,110,62), (rdraw.right - 20, rdraw.centery), 9)
            if hovered: hover_name = name
            y += r.h + 14
        self.surface.set_clip(clip_prev)
        self._draw_scrollbar_left()

        # Detail panel
        pygame.draw.rect(self.surface, (244,242,238), self.detail_rect, border_radius=8)
        pygame.draw.rect(self.surface, (190,186,178), self.detail_rect, 1, border_radius=8)
        lines = [
            "Bars (top→bottom): PP, WAR, ARMS, SPACE.",
            "Length meaning: PP/WAR are relative to the strongest candidate right now; ARMS/SPACE are relative to tier 5 (max).",
            "Numbers on the left are the exact values."
        ]
        if hover_name:
            c = self._country_by_name(hover_name)
            lines.append("")
            lines.append(f"{hover_name} — PP {int(getattr(c,'pp',0))}, WAR {int(getattr(c,'war_power',0))}, ARMS {int(getattr(c,'arms_race',0))}, SPACE {int(getattr(c,'space_race',0))}")
        yy = self.detail_rect.y + 10
        for ln in self._wrap_text(" ".join(lines), self.font_small, self.detail_rect.w - 20):
            surf = self.font_small.render(ln, True, self.col_muted); self.surface.blit(surf, (self.detail_rect.x + 10, yy)); yy += surf.get_height() + 2

        # Right column frame
        pygame.draw.rect(self.surface, (248,246,242), self.voters_rect, border_radius=10)
        pygame.draw.rect(self.surface, (190,186,178), self.voters_rect, 1, border_radius=10)

        # Titles inside right column
        vx, vy = self.voters_rect.x + 12, self.voters_rect.y + 12
        title2 = self.font_bold.render("VOTES IN PROGRESS", True, self.col_text)
        self.surface.blit(title2, (vx, vy)); vy += 8 + title2.get_height()

        # Voters list area (clipped + scroll)
        self.surface.set_clip(self.voters_list_rect)
        self._draw_voters_scrolled(self.voters_list_rect)
        self.surface.set_clip(None)
        self._draw_scrollbar_generic(self.voters_list_rect, self._voters_content_h, self._voters_scroll_y)

        # Tally title
        t_title = self.font_bold.render("TALLY:", True, self.col_text)
        ttx = self.voters_rect.x + 12
        tty = self.voters_list_rect.bottom + 12
        self.surface.blit(t_title, (ttx, tty))

        # Tally list area
        self.surface.set_clip(self.tally_list_rect)
        self._draw_tally_scrolled(self.tally_list_rect)
        self.surface.set_clip(None)
        self._draw_scrollbar_generic(self.tally_list_rect, self._tally_content_h, self._tally_scroll_y)

        # Confirm button
        enabled = self._human_choice is not None
        bg = self.col_btn_ok if enabled else self.col_btn_disabled
        pygame.draw.rect(self.surface, bg, self.btn_confirm_rect, border_radius=12)
        pygame.draw.rect(self.surface, self.col_border, self.btn_confirm_rect, 2, border_radius=12)
        label = self.font_body.render("CONFIRM VOTE", True, (245,245,245))
        lrect = label.get_rect(); lrect.center = self.btn_confirm_rect.center
        self.surface.blit(label, lrect)

    def _draw_result_overlay(self):
        # Small centered chip telling the winner and prompting to continue
        if not self._result_chosen: return
        name = getattr(self._result_chosen, 'name', str(self._result_chosen))
        txt = f"Result: {name} will defect"
        sub = "Click to continue"
        base = pygame.Surface((self.panel_rect.w - 120, 120), pygame.SRCALPHA)
        pygame.draw.rect(base, (20,20,20,210), base.get_rect(), border_radius=12)
        t1 = self.font_body.render(txt, True, (240,240,240))
        t2 = self.font_small.render(sub, True, (220,220,220))
        base.blit(t1, (20, 24)); base.blit(t2, (20, 24 + t1.get_height() + 8))
        brect = base.get_rect(); brect.center = self.panel_rect.center
        self.surface.blit(base, brect)

    def _draw_ejection_popup(self):
        # Big, dramatic full-screen popup
        sw, sh = self.surface.get_size()
        now = pygame.time.get_ticks()
        if self._eject_start_ms is None:
            self._eject_start_ms = now
        t = (now - self._eject_start_ms) / 1000.0

        # Flashing background
        flash = 60 + int(40 * (0.5 + 0.5 * math.sin(t * 6.0)))
        bg = pygame.Surface((sw, sh)); bg.fill((flash+80, 30, 30))
        self.surface.blit(bg, (0,0))
        self.surface.blit(self._overlay, (0,0))

        # Text with slight pulse / shadow
        name = self._eject_name or "UNKNOWN"
        line1 = f"{name}"
        line2 = "WAS EJECTED"
        scale = 1.0 + 0.02 * math.sin(t * 5.0)

        def _render_big(s, col):
            f = self.font_big
            surf = f.render(s, True, col)
            w, h = surf.get_size();
            surf = pygame.transform.smoothscale(surf, (int(w*scale), int(h*scale)))
            return surf

        txt1 = _render_big(line1, (245,245,245))
        txt2 = _render_big(line2, (245,245,245))
        shadow1 = _render_big(line1, (20,20,20))
        shadow2 = _render_big(line2, (20,20,20))

        # Position
        y = sh//2 - txt1.get_height()
        x1 = (sw - txt1.get_width())//2
        x2 = (sw - txt2.get_width())//2
        self.surface.blit(shadow1, (x1+4, y+4)); self.surface.blit(txt1, (x1, y))
        self.surface.blit(shadow2, (x2+4, y + txt1.get_height() + 16 + 4))
        self.surface.blit(txt2, (x2, y + txt1.get_height() + 16))

        hint = self.font_small.render("Click to continue", True, (240,240,240))
        self.surface.blit(hint, ((sw - hint.get_width())//2, int(sh*0.82)))

    # ----------------------- Internals -----------------------
    def _draw_voters_scrolled(self, area: pygame.Rect):
        pygame.draw.rect(self.surface, (248,246,242), area, border_radius=8)
        pygame.draw.rect(self.surface, (190,186,178), area, 1, border_radius=8)
        line_h = self.font_small.get_height() + 6
        y = area.y + 8 - self._voters_scroll_y
        self._voters_content_h = 8
        for v in self._voters:
            status = self._ai_choice.get(v.name)
            line = f"{v.name} — "
            if v is self._human:
                line += ("(YOU) ") + (f"selected {self._human_choice}" if self._human_choice else "selecting…")
            elif getattr(v, 'is_ai', False):
                if status is None and v.name in self._ai_due:
                    ms_left = max(0, self._ai_due[v.name] - pygame.time.get_ticks())
                    line += f"thinking ({ms_left//1000}.{(ms_left%1000)//100}s)"
                elif status is None: line += "thinking…"
                else: line += f"voted {status}"
            else:
                line += (f"voted {status}" if status else "selecting…")
            t = self.font_small.render(line, True, self.col_text)
            ty = y
            if ty + t.get_height() >= area.top and ty <= area.bottom:
                self.surface.blit(t, (area.x + 10, ty))
            y += line_h
            self._voters_content_h += line_h
        self._clamp_voters_scroll()

    def _draw_tally_scrolled(self, area: pygame.Rect):
        pygame.draw.rect(self.surface, (248,246,242), area, border_radius=8)
        pygame.draw.rect(self.surface, (190,186,178), area, 1, border_radius=8)
        line_h = self.font_small.get_height() + 2
        y = area.y + 8 - self._tally_scroll_y
        self._tally_content_h = 8
        for name, count in sorted(self._tally.items(), key=lambda kv: (-kv[1], kv[0])):
            ln = f"{name}: {count}"
            t = self.font_small.render(ln, True, self.col_muted)
            if y + t.get_height() >= area.top and y <= area.bottom:
                self.surface.blit(t, (area.x + 10, y))
            y += line_h
            self._tally_content_h += line_h
        self._clamp_tally_scroll()

    def _draw_stat_rows(self, rdraw: pygame.Rect, c: object):
        # Four rows: label/value at left, bar to the right
        pad_x = 14; top = rdraw.y + 56
        label_w = 120
        bar_x = rdraw.x + pad_x + label_w
        bar_w = rdraw.w - (bar_x - rdraw.x) - 20
        bar_h = 8; gap = 8
        pp = float(getattr(c, 'pp', 0)); war = float(getattr(c, 'war_power', 0))
        arms = float(getattr(c, 'arms_race', 0)); space = float(getattr(c, 'space_race', 0))
        pp_n = 0.0 if self._pp_max <= 0 else min(1.0, pp / self._pp_max)
        war_n = 0.0 if self._war_max <= 0 else min(1.0, war / self._war_max)
        arms_n = min(1.0, arms / 5.0)
        space_n = min(1.0, space / 5.0)
        items = [
            ("PP", int(pp), pp_n, self.col_bar_pp),
            ("WAR", int(war), war_n, self.col_bar_war),
            ("ARMS", int(arms), arms_n, self.col_bar_arms),
            ("SPACE", int(space), space_n, self.col_bar_space),
        ]
        for i, (label, val, norm, col) in enumerate(items):
            y = top + i*(bar_h+gap)
            left_text = self.font_mono.render(f"{label} {val}", True, self.col_muted)
            self.surface.blit(left_text, (rdraw.x + pad_x, y - 3))
            rail = pygame.Rect(bar_x, y, bar_w, bar_h)
            pygame.draw.rect(self.surface, self.col_bar_bg, rail, border_radius=3)
            w = int(bar_w * norm)
            if w > 0:
                pygame.draw.rect(self.surface, col, (bar_x, y, w, bar_h), border_radius=3)

    def _rebuild_item_rects(self):
        sw, sh = self.surface.get_size()
        self.panel_rect.size = (min(1200, int(sw * 0.86)), min(760, int(sh * 0.82)))
        self.panel_rect.center = (sw // 2, sh // 2)
        self.header_rect.size = (self.panel_rect.w, 104)
        self.header_rect.topleft = self.panel_rect.topleft
        self.body_rect.size = (self.panel_rect.w, self.panel_rect.h - self.header_rect.h)
        self.body_rect.topleft = (self.panel_rect.x, self.header_rect.bottom)
        pad = 22
        inner = self.body_rect.inflate(-pad*2, -pad*2)
        self.list_rect.size = (int(inner.w * 0.60), int(inner.h * 0.68))
        self.list_rect.topleft = inner.topleft
        self.detail_rect.size = (self.list_rect.w, inner.h - self.list_rect.h - 12)
        self.detail_rect.topleft = (self.list_rect.x, self.list_rect.bottom + 12)
        self.voters_rect.size = (inner.w - self.list_rect.w - 20, self.list_rect.h + 120)
        self.voters_rect.topleft = (self.list_rect.right + 20, self.list_rect.y)
        self.btn_confirm_rect.size = (min(340, self.voters_rect.w), 60)
        self.btn_confirm_rect.topright = (self.voters_rect.right, self.detail_rect.bottom - 4)
        # Left list content rects
        self._item_rects.clear()
        if not self._eligible: return
        y = 12; x = 12; item_w = self.list_rect.w - 24; item_h = 122
        gap = 14
        for e in self._eligible:
            self._item_rects.append((pygame.Rect(x, y, item_w, item_h), e.name)); y += item_h + gap
        # Right column sub-areas (voters / tally)
        header_h = 30
        self.voters_list_rect = pygame.Rect(
            self.voters_rect.x + 10,
            self.voters_rect.y + header_h + 8,
            self.voters_rect.w - 20,
            int(self.voters_rect.h * 0.52)
        )
        tally_title_h = 24
        self.tally_list_rect = pygame.Rect(
            self.voters_rect.x + 10,
            self.voters_list_rect.bottom + tally_title_h + 12,
            self.voters_rect.w - 20,
            self.voters_rect.bottom - (self.voters_list_rect.bottom + tally_title_h + 22)
        )

    def _recompute_content_height(self):
        if not self._item_rects: self._content_h = 0
        else:
            last_rect, _ = self._item_rects[-1]; self._content_h = last_rect.bottom + 12
        self._clamp_left_scroll()

    def _clamp_left_scroll(self):
        view_h = self.list_rect.h - 24; max_scroll = max(0, self._content_h - view_h)
        self._scroll_y = max(0, min(self._scroll_y, max_scroll))

    def _clamp_voters_scroll(self):
        view_h = max(0, self.voters_list_rect.h - 16)
        max_scroll = max(0, self._voters_content_h - view_h)
        self._voters_scroll_y = max(0, min(self._voters_scroll_y, max_scroll))

    def _clamp_tally_scroll(self):
        view_h = max(0, self.tally_list_rect.h - 16)
        max_scroll = max(0, self._tally_content_h - view_h)
        self._tally_scroll_y = max(0, min(self._tally_scroll_y, max_scroll))

    def _draw_scrollbar_left(self):
        if self._content_h <= self.list_rect.h - 24: return
        track = pygame.Rect(self.list_rect.right - 8, self.list_rect.top + 6, 4, self.list_rect.h - 12)
        pygame.draw.rect(self.surface, self.col_scroll_track, track, border_radius=2)
        ratio = (self.list_rect.h - 24) / float(self._content_h)
        knob_h = max(24, int(track.height * ratio))
        max_offset = max(1, self._content_h - (self.list_rect.h - 24))
        offset_ratio = self._scroll_y / max_offset
        knob_y = int(track.y + (track.height - knob_h) * offset_ratio)
        knob = pygame.Rect(track.x - 2, knob_y, 8, knob_h)
        pygame.draw.rect(self.surface, self.col_scroll_knob, knob, border_radius=3)

    def _draw_scrollbar_generic(self, rect: pygame.Rect, content_h: int, scroll_y: int):
        if content_h <= rect.h - 16: return
        track = pygame.Rect(rect.right - 6, rect.top + 6, 3, rect.h - 12)
        pygame.draw.rect(self.surface, self.col_scroll_track, track, border_radius=2)
        ratio = (rect.h - 16) / float(content_h)
        knob_h = max(20, int(track.height * ratio))
        max_offset = max(1, content_h - (rect.h - 16))
        offset_ratio = scroll_y / max_offset
        knob_y = int(track.y + (track.height - knob_h) * offset_ratio)
        knob = pygame.Rect(track.x - 2, knob_y, 7, knob_h)
        pygame.draw.rect(self.surface, self.col_scroll_knob, knob, border_radius=3)

    def _country_by_name(self, name: str):
        for e in self._eligible:
            if e.name == name: return e
        for v in self._voters:
            if v.name == name: return v
        return None

    def _try_finish(self):
        all_ai_done = all(ch is not None for ch in self._ai_choice.values())
        if self._human_confirmed and all_ai_done:
            if self._human_choice is not None:
                self._tally[self._human_choice] = self._tally.get(self._human_choice, 0) + 1
                self._order.append((self._human.name, self._human_choice))
            # pick winner but DO NOT reset/callback yet — show RESULT then EJECT popup
            winner_name = max(self._tally.items(), key=lambda kv: (kv[1], -ord(kv[0][0]) if kv[0] else 0))[0]
            self._result_chosen = self._country_by_name(winner_name)
            self._result_tally = dict(self._tally)
            self._result_order = list(self._order)
            self.state = self.RESULT

    def _start_ejection_popup(self):
        self._eject_name = getattr(self._result_chosen, 'name', 'UNKNOWN')
        self._eject_start_ms = pygame.time.get_ticks()
        self.state = self.EJECT

    def _finalize_and_callback(self):
        cb = self._on_result
        chosen_obj = self._result_chosen
        tally_copy = self._result_tally or {}
        order_copy = self._result_order or []
        # reset internal state first
        self._reset()
        # callback
        if cb:
            cb(chosen_obj, tally_copy, order_copy)

    def _reset(self):
        self._voters = []; self._eligible = []; self._human = None; self._on_result = None
        self._desc_fn = None; self._weight_fn = None
        self._ai_due.clear(); self._ai_choice.clear(); self._tally.clear(); self._order.clear()
        self._human_choice = None; self._human_confirmed = False
        self._scroll_y = 0; self._content_h = 0
        self._voters_scroll_y = 0; self._tally_scroll_y = 0
        self._result_chosen = None; self._result_tally = None; self._result_order = None
        self._eject_name = None; self._eject_start_ms = None
        self.state = self.IDLE

    def _weighted_choice(self) -> str:
        # Only PP, War Power, Arms, Space determine AI votes (weaker/less advanced more likely to defect)
        base = 0.2; a, b, c, d = 0.8, 0.8, 0.6, 0.6
        names: List[str] = []; weights: List[float] = []
        for e in self._eligible:
            names.append(e.name)
            pp = float(getattr(e, 'pp', 0)); war = float(getattr(e, 'war_power', 0))
            arms = float(getattr(e, 'arms_race', 0)); space = float(getattr(e, 'space_race', 0))
            pp_d = 1.0 - (0.0 if self._pp_max <= 0 else min(1.0, pp / self._pp_max))
            war_d = 1.0 - (0.0 if self._war_max <= 0 else min(1.0, war / self._war_max))
            arms_d = 1.0 - min(1.0, arms / 5.0)
            space_d = 1.0 - min(1.0, space / 5.0)
            w = base + a*pp_d + b*war_d + c*arms_d + d*space_d + random.random()*0.2
            weights.append(max(0.05, w))
        total = sum(weights); r = random.random() * total; acc = 0.0
        for name, w in zip(names, weights):
            acc += w
            if r <= acc: return name
        return names[-1]

    def _wrap_text(self, text: str, font: pygame.font.Font, max_w: int) -> List[str]:
        words = text.split(); lines = []; cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= max_w: cur = test
            else: lines.append(cur); cur = w
        if cur: lines.append(cur)
        return lines

    def on_resize(self, size: Tuple[int, int]):
        sw, sh = size
        self._overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, self.overlay_alpha))
        self._rebuild_item_rects()


# --------------------------- DEMO ---------------------------
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((1280, 820), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    class _C:
        def __init__(self, name, pp, is_ai=True):
            self.name = name; self.pp = pp; self.is_ai = is_ai
            self.arms_race = random.randint(0, 5)
            self.space_race = random.randint(0, 5)
            self.war_power = random.randint(8, 20)
            self.bloc = None

    class _Bloc:
        def __init__(self, name):
            self.name = name; self.countries: List[_C] = []

    warsaw = _Bloc("Warsaw Pact"); non_aligned = _Bloc("Non-Aligned")
    pool = [
        _C("USSR", 1310, True), _C("Poland", 110, False), _C("East Germany", 90, True),
        _C("Czechoslovakia", 63, True), _C("Hungary", 38, True), _C("Romania", 34, True),
        _C("Bulgaria", 12, True), _C("North Korea", 26, True), _C("Albania", 80, True), _C("Yugoslavia", 210, True),
    ]
    for c in pool: c.bloc = "Warsaw Pact"; warsaw.countries.append(c)

    def get_bloc_members(name: str) -> List[_C]:
        if name == "Warsaw Pact": return list(warsaw.countries)
        if name == "Non-Aligned": return list(non_aligned.countries)
        return []

    human = next(c for c in pool if c.name == "Poland")

    mgr = BlocMemberVoteManager(screen, get_bloc_members=get_bloc_members)

    def on_done(chosen_obj, tally, order):
        print("WINNER:", getattr(chosen_obj, 'name', chosen_obj))
        print("TALLY:", tally); print("ORDER:", order)
        # mutate blocs as usual
        if chosen_obj in warsaw.countries: warsaw.countries.remove(chosen_obj)
        chosen_obj.bloc = "Non-Aligned"; non_aligned.countries.append(chosen_obj)

    mgr.start_vote_for_bloc(
        bloc_name="Warsaw Pact", human_country=human, eligible_names=None,
        on_result=on_done, title="WARSAW -> NON-ALIGNED",
        subtitle="Select the member that defects",
        desc_fn=None, weight_fn=None, ai_delay_range_ms=(9000, 18000))

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: running = False
            mgr.handle_event(event)
        mgr.update(dt)
        screen.fill((32, 38, 52))
        pygame.draw.rect(screen, (38, 46, 62), pygame.Rect(0, 0, screen.get_width(), 70))
        cap = pygame.font.SysFont("Segoe UI", 24, bold=True).render("Cold War — Bloc Vote + EJECTION Popup Demo", True, (220, 226, 232))
        screen.blit(cap, (16, 16))
        mgr.draw(); pygame.display.flip()
    pygame.quit()
