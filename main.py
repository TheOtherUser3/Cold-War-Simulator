import logging
import sys
import random
import pygame
from setup import init_countries_and_blocs
from gamestate import *

WINDOW_WIDTH, WINDOW_HEIGHT = 1280, 800
FPS = 60
BG_COLOR = (30, 33, 40)
BTN_W, BTN_H = 400, 80
BUTTON_COLOR = (80, 120, 200)
BUTTON_HOVER = (120, 160, 240)
BUTTON_TEXT_COLOR = (255, 255, 255)

def draw_button(screen, rect, text, font, hovered):
    color = BUTTON_HOVER if hovered else BUTTON_COLOR
    pygame.draw.rect(screen, color, rect, border_radius=18)
    label = font.render(text, True, BUTTON_TEXT_COLOR)
    label_rect = label.get_rect(center=rect.center)
    screen.blit(label, label_rect)

def main():
    blocs, countries = init_countries_and_blocs()
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Cold War Simulation")
    clock = pygame.time.Clock()
    Game = GameState(screen, blocs, countries)

    tooltip_font = pygame.font.SysFont("consolas,menlo,dejavusansmono,monospace", 18)

    font = pygame.font.SysFont("Segoe UI", 36)
    btn_rect = pygame.Rect(0, 0, BTN_W, BTN_H)
    btn_rect.center = (WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)

    show_title = True
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
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and hover and show_title:
                #Game.coup_spinner(Game.country("United Kingdom"), Game.country("Afghanistan"))
                #Game.coin_flip()
                show_title = False

            # --- overlay managers ---
            if Game.coin_mgr.is_active():
                Game.coin_mgr.handle_event(event)
            if Game.spinner_mgr.is_active():
                Game.spinner_mgr.handle_event(event)
            if Game.dice_mgr.is_active():
                Game.dice_mgr.handle_event(event)
            if hasattr(Game, "war_mgr") and Game.war_mgr and Game.war_mgr.is_active():
                Game.war_mgr.handle_event(event)

        # --- overlay updates ---
        if Game.coin_mgr.is_active():
            Game.coin_mgr.update(clock.get_time() / 1000.0)
        if Game.spinner_mgr.is_active():
            Game.spinner_mgr.update(clock.get_time() / 1000.0)
        if Game.dice_mgr.is_active():
            Game.dice_mgr.update(clock.get_time() / 1000.0)
        if hasattr(Game, "war_mgr") and Game.war_mgr and Game.war_mgr.is_active():
            Game.war_mgr.update(clock.get_time() / 1000.0)

        screen.fill(BG_COLOR)

        if show_title:
            title = font.render("Cold War Simulation", True, (220, 220, 255))
            screen.blit(title, title.get_rect(center=(screen.get_width() // 2, 140)))
            draw_button(screen, btn_rect, "Start Coup Spinner", font, hover)

        # --- overlay draws ---
        if Game.coin_mgr.is_active():
            Game.coin_mgr.draw()
        if Game.spinner_mgr.is_active():
            Game.spinner_mgr.draw()
        if Game.dice_mgr.is_active():
            Game.dice_mgr.draw()
        if hasattr(Game, "war_mgr") and Game.war_mgr and Game.war_mgr.is_active():
            Game.war_mgr.draw()

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
