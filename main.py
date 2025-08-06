import logging
import sys
import random

import pygame
from War import War
from setup import init_countries_and_blocs
from gamestate import *

# --------------------------------------------------
# Logging
# --------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('game.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("game")

# --------------------------------------------------
# Constants & Helpers
# --------------------------------------------------
WINDOW_WIDTH, WINDOW_HEIGHT = 1280, 800
FPS = 60
BG_COLOR = (30, 33, 40)
CARD_W, CARD_H = 240, 180
BTN_W, BTN_H = 240, 80
BUTTON_COLOR = (80, 120, 200)
BUTTON_HOVER = (120, 160, 240)
BUTTON_TEXT_COLOR = (255, 255, 255)
NUM_COLOR = (20, 20, 30)

def draw_button(screen: pygame.Surface, rect: pygame.Rect, text: str, font, hovered: bool):
    color = BUTTON_HOVER if hovered else BUTTON_COLOR
    pygame.draw.rect(screen, color, rect, border_radius=18)
    label = font.render(text, True, BUTTON_TEXT_COLOR)
    label_rect = label.get_rect(center=rect.center)
    screen.blit(label, label_rect)

def load_image(card):
    try:
        img = pygame.image.load(card.image).convert_alpha()
        return pygame.transform.smoothscale(img, (CARD_W, CARD_H))
    except Exception:
        surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        surf.fill((90, 90, 110))
        return surf

def random_pos(side: int, scr_w: int, scr_h: int, n: int):
    if side == 0:
        x_left = 40 + n * 10
        x_right = scr_w // 2 - CARD_W - 40
        y_top = 120
        y_bot = scr_h // 2 - CARD_H - 60
    else:
        x_left = scr_w // 2 + 40
        x_right = scr_w - CARD_W - 40 - n * 10
        y_top = scr_h // 2 + 80
        y_bot = scr_h - CARD_H - 120

    if x_left > x_right:
        x_left, x_right = x_right, x_left
    if y_top > y_bot:
        y_top, y_bot = y_bot, y_top

    x = random.randint(x_left, x_right)
    y = random.randint(y_top, y_bot)
    return x, y

# --------------------------------------------------
# Main game loop
# --------------------------------------------------
def main():
    blocs, countries = init_countries_and_blocs()
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Cold War Simulation")
    clock = pygame.time.Clock()
    Game = GameState(screen, blocs, countries)

    font = pygame.font.SysFont("Segoe UI", 36)
    small_font = pygame.font.SysFont("Segoe UI", 24)
    tiny_font = pygame.font.SysFont("Segoe UI", 18)
    num_font = pygame.font.SysFont("Segoe UI", 40, bold=True)

    war = None
    show_title = True
    game_over = False
    winner = None

    attacker_card = defender_card = None
    round_msg = None

    face_down_attk = []
    face_down_def = []

    btn_rect = pygame.Rect(0, 0, BTN_W, BTN_H)
    btn_rect.center = (WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)

    def new_game():
        nonlocal war, game_over, winner, attacker_card, defender_card, round_msg
        nonlocal face_down_attk, face_down_def, show_title
        war = War(screen, Game.country("USA"), Game.country("USSR"))
        game_over = False
        winner = None
        attacker_card = defender_card = None
        round_msg = None
        face_down_attk.clear()
        face_down_def.clear()
        show_title = False
        logger.info("New game started – attacker & defender both have 10 cards.")

    running = True
    while running:
        mouse = pygame.mouse.get_pos()
        hover = btn_rect.collidepoint(mouse)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                btn_rect.center = (screen.get_width() // 2, screen.get_height() // 2)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and hover:
                Game.coup_spinner(Game.countries["USA"], Game.countries["USSR"])
                if war is None:
                    new_game()
                    continue
                if game_over:
                    new_game()
                    continue
                step = war.next_round()
                phase = step["phase"]
                if phase == "war_face_down":
                    x, y = random_pos(0, screen.get_width(), screen.get_height(), len(face_down_attk))
                    face_down_attk.append((x, y))
                    x, y = random_pos(1, screen.get_width(), screen.get_height(), len(face_down_def))
                    face_down_def.append((x, y))
                    rd = step.get("face_downs_remaining", 0)
                    round_msg = f"War! {rd} face‑down remaining…"
                elif phase == "war_battle":
                    attacker_card = step.get("attacker_card")
                    defender_card = step.get("defender_card")
                    if step.get("winner") is None:
                        fd_left = step.get("face_downs_remaining", 0)
                        round_msg = "Tie again! Starting new war…" if fd_left else "Tie again!…"
                    else:
                        round_msg = f"{step['winner'].capitalize()} wins the war!"
                        face_down_attk.clear()
                        face_down_def.clear()
                elif phase == "normal":
                    attacker_card = step["attacker_card"]
                    defender_card = step["defender_card"]
                    if step["winner"] is None:
                        fd_left = step.get("face_downs_remaining", 0)
                        round_msg = "Tie! Starting war…" if fd_left else "Tie!…"
                    else:
                        round_msg = f"{step['winner'].capitalize()} wins the round!"
                        face_down_attk.clear()
                        face_down_def.clear()
                has_won, vict = war.has_won()
                if has_won:
                    game_over = True
                    winner = vict
                    attacker_card = defender_card = None
                    round_msg = f"{vict.capitalize()} wins the war! Click to restart."

            # ----------OVERLAY MANAGE EVENTS ----------
        if Game.spinner_mgr.is_active():
            Game.spinner_mgr.handle_event(event)
        if Game.dice_mgr.is_active():
            Game.dice_mgr.handle_event(event)

        # ---------- OVERLAY MANAGE UPDATE ----------
        if Game.spinner_mgr.is_active():
            Game.spinner_mgr.update(clock.get_time() / 1000.0)
        if Game.dice_mgr.is_active():
            Game.dice_mgr.update(clock.get_time() / 1000.0)
            
        screen.fill(BG_COLOR)
        if war is not None:
            atk_d, atk_s = len(war.attacker_hand.cards), len(war.attacker_hand.spoils)
            def_d, def_s = len(war.defender_hand.cards), len(war.defender_hand.spoils)
            atk_label = small_font.render("Attacker", True, (200, 255, 255))
            atk_rect = atk_label.get_rect(center=(screen.get_width() // 2, 40))
            screen.blit(atk_label, atk_rect)
            atk_info = tiny_font.render(f"Deck: {atk_d}  Spoils: {atk_s}  Total: {atk_d + atk_s}", True, (200, 255, 255))
            screen.blit(atk_info, atk_info.get_rect(center=(screen.get_width() // 2, 65)))
            def_label = small_font.render("Defender", True, (255, 210, 180))
            screen.blit(def_label, def_label.get_rect(center=(screen.get_width() // 2, screen.get_height() - 80)))
            def_info = tiny_font.render(f"Deck: {def_d}  Spoils: {def_s}  Total: {def_d + def_s}", True, (255, 210, 180))
            screen.blit(def_info, def_info.get_rect(center=(screen.get_width() // 2, screen.get_height() - 50)))
        for pos in face_down_attk:
            pygame.draw.rect(screen, (90, 90, 120), (*pos, CARD_W, CARD_H), border_radius=12)
        for pos in face_down_def:
            pygame.draw.rect(screen, (120, 100, 90), (*pos, CARD_W, CARD_H), border_radius=12)
        if attacker_card:
            img = load_image(attacker_card)
            ir = img.get_rect(center=(screen.get_width() // 2, 180))
            screen.blit(img, ir)
            num = num_font.render(str(attacker_card.value + 1), True, NUM_COLOR)
            screen.blit(num, num.get_rect(topright=(ir.right - 10, ir.top + 6)))
        if defender_card:
            img = load_image(defender_card)
            ir = img.get_rect(center=(screen.get_width() // 2, screen.get_height() - 200))
            screen.blit(img, ir)
            num = num_font.render(str(defender_card.value + 1), True, NUM_COLOR)
            screen.blit(num, num.get_rect(topright=(ir.right - 10, ir.top + 6)))
        if round_msg:
            txt = font.render(round_msg, True, (255, 255, 220))
            screen.blit(txt, txt.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 - 90)))
        if show_title:
            title = font.render("Cold War Simulation", True, (220, 220, 255))
            screen.blit(title, title.get_rect(center=(screen.get_width() // 2, 60)))
        btn_label = (
            "Start War" if war is None else
            f"{winner.capitalize()} wins! (Restart)" if game_over else
            "Next Round"
        )
        draw_button(screen, btn_rect, btn_label, font, hover)

        # ---------- OVERLAY MANAGER DRAW ----------
        if Game.spinner_mgr.is_active():
            Game.spinner_mgr.draw()
        if Game.dice_mgr.is_active():
            Game.dice_mgr.draw()

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
