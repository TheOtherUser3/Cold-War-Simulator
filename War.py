# -*- coding: utf-8 -*-
"""
Created on Sun Nov 17 18:35:17 2024

@author: dawso
"""
import random
import logging
import pygame


logger = logging.getLogger("war")
logger.setLevel(logging.INFO)

# remove all handlers that are already there
if logger.hasHandlers():
    logger.handlers.clear()

file_handler   = logging.FileHandler("war.log", mode="a")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))

logger.addHandler(file_handler)
logger.addHandler(stream_handler)
logger.propagate = False

# use it:
logger.info("War module initialised")


class WarManager:
    def __init__(self, screen, attacker, defender, fonts, on_result=None):
        self.screen = screen
        self.font, self.small_font, self.tiny_font, self.num_font = fonts
        self.on_result = on_result
        self.war = War(screen, attacker, defender)
        self.attacker = attacker
        self.defender = defender
        self.face_down_attk = []
        self.face_down_def = []
        self.attacker_card = None
        self.defender_card = None
        self.round_msg = None
        self.game_over = False
        self.winner = None

        self.btn_rect = pygame.Rect(0, 0, 240, 80)
        self.btn_rect.center = (screen.get_width() // 2, screen.get_height() // 2)

    def is_active(self):
        return not self.game_over

    def handle_event(self, event):
        mouse = pygame.mouse.get_pos()
        hover = self.btn_rect.collidepoint(mouse)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and hover:
            if self.game_over:
                # War is over. Notify parent via callback and reset
                if self.on_result:
                    self.on_result(self.winner)
                self.reset()
                return
            step = self.war.next_round()
            phase = step["phase"]
            if phase == "war_face_down":
                x, y = self.random_pos(0, self.screen.get_width(), self.screen.get_height(), len(self.face_down_attk))
                self.face_down_attk.append((x, y))
                x, y = self.random_pos(1, self.screen.get_width(), self.screen.get_height(), len(self.face_down_def))
                self.face_down_def.append((x, y))
                rd = step.get("face_downs_remaining", 0)
                self.round_msg = f"War! {rd} face-down remaining…"
            elif phase == "war_battle":
                self.attacker_card = step.get("attacker_card")
                self.defender_card = step.get("defender_card")
                winner = step.get("winner")
                if winner is None:
                    fd_left = step.get("face_downs_remaining", 0)
                    self.round_msg = "Tie again! Starting new war…" if fd_left else "Tie again!…"
                else:
                    winner_name = winner.name if winner is not None else ""
                    self.round_msg = f"{winner_name} wins the war!"
                    self.face_down_attk.clear()
                    self.face_down_def.clear()
            elif phase == "normal":
                self.attacker_card = step["attacker_card"]
                self.defender_card = step["defender_card"]
                winner = step.get("winner")
                if winner is None:
                    fd_left = step.get("face_downs_remaining", 0)
                    self.round_msg = "Tie! Starting war…" if fd_left else "Tie!…"
                else:
                    winner_name = winner.name if winner is not None else ""
                    self.round_msg = f"{winner_name} wins the round!"
                    self.face_down_attk.clear()
                    self.face_down_def.clear()
            has_won, vict = self.war.has_won()
            if has_won:
                self.game_over = True
                self.winner = vict
                self.attacker_card = self.defender_card = None
                winner_name = vict.name if vict is not None else ""
                self.round_msg = f"{winner_name} wins the war! Click to continue."


    def update(self, dt):
        pass  # placeholder for any future animation/timing

    def draw(self):
        # --- Deck info ---
        atk_d, atk_s = len(self.war.attacker_hand.cards), len(self.war.attacker_hand.spoils)
        def_d, def_s = len(self.war.defender_hand.cards), len(self.war.defender_hand.spoils)
        atk_label = self.small_font.render(f"Attacker ({self.attacker.name})", True, (200, 255, 255))
        atk_rect = atk_label.get_rect(center=(self.screen.get_width() // 2, 40))
        self.screen.blit(atk_label, atk_rect)
        atk_info = self.tiny_font.render(f"Deck: {atk_d}  Spoils: {atk_s}  Total: {atk_d + atk_s}", True, (200, 255, 255))
        self.screen.blit(atk_info, atk_info.get_rect(center=(self.screen.get_width() // 2, 65)))
        def_label = self.small_font.render(f"Defender ({self.defender.name})", True, (255, 210, 180))
        self.screen.blit(def_label, def_label.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() - 80)))
        def_info = self.tiny_font.render(f"Deck: {def_d}  Spoils: {def_s}  Total: {def_d + def_s}", True, (255, 210, 180))
        self.screen.blit(def_info, def_info.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() - 50)))
        # --- Face down cards ---
        for pos in self.face_down_attk:
            pygame.draw.rect(self.screen, (90, 90, 120), (*pos, 240, 180), border_radius=12)
        for pos in self.face_down_def:
            pygame.draw.rect(self.screen, (120, 100, 90), (*pos, 240, 180), border_radius=12)
        # --- Played cards ---
        if self.attacker_card:
            img = self.load_image(self.attacker_card)
            ir = img.get_rect(center=(self.screen.get_width() // 2, 180))
            self.screen.blit(img, ir)
            num = self.num_font.render(str(self.attacker_card.value + 1), True, (20, 20, 30))
            self.screen.blit(num, num.get_rect(topright=(ir.right - 10, ir.top + 6)))
        if self.defender_card:
            img = self.load_image(self.defender_card)
            ir = img.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() - 200))
            self.screen.blit(img, ir)
            num = self.num_font.render(str(self.defender_card.value + 1), True, (20, 20, 30))
            self.screen.blit(num, num.get_rect(topright=(ir.right - 10, ir.top + 6)))
        # --- Message and title ---
        if self.round_msg:
            txt = self.font.render(self.round_msg, True, (255, 255, 220))
            self.screen.blit(txt, txt.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2 - 90)))
        # --- Button ---
        mouse = pygame.mouse.get_pos()
        hover = self.btn_rect.collidepoint(mouse)
        btn_label = (
            f"{self.winner.capitalize()} wins! (Continue)" if self.game_over else
            "Next Round"
        )
        self.draw_button(self.screen, self.btn_rect, btn_label, self.font, hover)

    def draw_button(self, screen, rect, text, font, hovered):
        color = (120, 160, 240) if hovered else (80, 120, 200)
        pygame.draw.rect(screen, color, rect, border_radius=18)
        label = font.render(text, True, (255, 255, 255))
        label_rect = label.get_rect(center=rect.center)
        screen.blit(label, label_rect)

    def load_image(self, card):
        try:
            img = pygame.image.load(card.image).convert_alpha()
            return pygame.transform.smoothscale(img, (240, 180))
        except Exception:
            surf = pygame.Surface((240, 180), pygame.SRCALPHA)
            surf.fill((90, 90, 110))
            return surf

    def random_pos(self, side, scr_w, scr_h, n):
        if side == 0:
            x_left = 40 + n * 10
            x_right = scr_w // 2 - 240 - 40
            y_top = 120
            y_bot = scr_h // 2 - 180 - 60
        else:
            x_left = scr_w // 2 + 40
            x_right = scr_w - 240 - 40 - n * 10
            y_top = scr_h // 2 + 80
            y_bot = scr_h - 180 - 120

        if x_left > x_right:
            x_left, x_right = x_right, x_left
        if y_top > y_bot:
            y_top, y_bot = y_bot, y_top

        x = random.randint(x_left, x_right)
        y = random.randint(y_top, y_bot)
        return x, y

    def reset(self):
        self.face_down_attk.clear()
        self.face_down_def.clear()
        self.attacker_card = None
        self.defender_card = None
        self.round_msg = None
        self.game_over = False
        self.winner = None

class Card:
    def __init__(self, value):
        self.image = f"cards/{value}.png"
        self.value = value
    
    def wins(self, other):
        return self.value > other.value
    
class Hand:
    """
    Represents a hand of cards for one participant (attacker or defender).
    Each card in the hand is drawn from the shared deck.
    Spoils represent cards won in tied rounds, which get shuffled back in if the hand runs out.
    """
    
    def __init__(self, length, deck):
        self.cards = []      # Cards available to play
        self.spoils = []     # Spoils won from ties (collected until recycled)
        for i in range(length):
            if len(deck) == 0:
                [[deck.append(i) for i in range(15)] for j in range(4)]
                random.shuffle(deck)
            self.add(deck.pop())
        
    def add(self, value):
        """
        Add a card to this hand (by value); value should be 0–12.
        """
        self.cards.append(Card(value))
        logger.debug(f"Added card with value {value} to hand.")

    def __repr__(self):
        s = "["
        for i in range(len(self.cards) - 1):
            s += str(self.cards[i].value) + ", "
        s += str(self.cards[-1].value)
        s += "]"
        return s
    
    def is_loss(self):
        """
        Returns True if this hand has no more cards or spoils left—i.e., the player has lost.
        """
        if len(self.cards) + len(self.spoils) == 0:
            return True
        return False
    
    def check_empty(self):
        """
        If main hand runs out but spoils remain, reshuffle spoils into main hand.
        """
        if len(self.cards) == 0:
            random.shuffle(self.spoils)
            self.cards = self.spoils
            self.spoils = []
        
    def draw(self):
        """Draws a single Card object and returns it"""
        self.check_empty()
        card = self.cards.pop()
        return card
    
    def draw_num(self, num_cards):
        """Draws the number of cards specified (used for Wars)
        Returns:
            List of Card objects"""
        cards = []
        for i in range(num_cards):
            self.check_empty()
            card = self.cards.pop()
            cards.append(card)
            logger.info(f"Drew card for war: {card.value}")
        return cards

    def add_spoils(self, cards):
        """Adds cards to spoils pile
        Parameters:
            Cards (List[Card])"""
        self.spoils += cards
        logger.info(f"Added spoils: {[c.value for c in cards]} to hand.")
        
    def length(self):
        """Returns total number of remaining cards"""
        return len(self.cards) + len(self.spoils)
    
class War:
    """
    Main class for running a 'War' card battle between two countries/sides.
    Each side is given a number of cards based on their support (50PP = 1 card).
    """
    # TO DO: REWRITE TO START WITH ATTACKER AND DEFENDER COUNTRY OBJECTS AND NOT LENGTHS, THEN CAN ALSO IMPLEMENT REWARDS HERE
    # ALSO: IMPLEMENT TO HAVE SCREEN GO HERE AS INPUT AND DO ALL VISUALS LIEK THAT
    def __init__(self, screen, attacker, defender):
        """
        Initialize a new war with the given number of cards for each side.
        params:
            attacker_length (int): Number of cards/support for attacker.
            defender_length (int): Number of cards/support for defender.
        """
        # Create and shuffle a standard deck of 52 cards (4 of each value, 0-12)
        self.deck = []
        [[self.deck.append(i) for i in range(15)] for _ in range(4)]
        random.shuffle(self.deck)

        # Deal hands for each side based on support (number of cards)
        self.attacker = attacker
        self.defender = defender
        self.attacker_length = attacker.war_power
        self.defender_length = defender.war_power
        self.attacker_hand = Hand(self.attacker_length, self.deck)
        self.defender_hand = Hand(self.defender_length, self.deck)
        self.phase = "normal"  # "normal", "war_face_down", or "war_battle"
        self.war_cards_left = 0
        self.spoils_pile = []
        self.last_attacker_card = None
        self.last_defender_card = None
                

        logger.info(f"Initialized War: attacker cards = {self.attacker_length}, defender cards = {self.defender_length}")

    def has_won(self):
         """Determines if the game is over
         Returns:
             (True/False, attacker/defender)"""
         if self.attacker_hand.is_loss():
            logger.info(f"Defender {self.defender.name} has won the war!")
            return (True, self.defender)
         elif self.defender_hand.is_loss():
            logger.info(f"Attacker {self.attacker.name} has won the war!")
            return (True, self.attacker)
         else:
            return (False, "None")
    
    def next_round(self):
        """
        Advances the game by ONE visible step:
        - In 'normal', draws/compares cards. On tie, enters 'war_face_down'.
        - In 'war_face_down', each call places one face-down card per side.
        - In 'war_battle', each call draws & compares the war battle cards.
        Returns a dict describing the step for the UI.
        """
        # If we are currently placing face-down war cards
        if self.phase == "war_face_down":
            # Place one face-down card for each, if possible
            step = {}
            if self.war_cards_left > 0:
                if self.attacker_hand.length() > 0:
                    self.spoils_pile.append(self.attacker_hand.draw())
                if self.defender_hand.length() > 0:
                    self.spoils_pile.append(self.defender_hand.draw())
                self.war_cards_left -= 1
                step = {
                    "phase": "war_face_down",
                    "face_downs_remaining": self.war_cards_left
                }
                # When all face-downs placed, next call will draw battle cards
                if self.war_cards_left == 0:
                    self.phase = "war_battle"
                return step
    
        # If it's time to flip battle cards during a war
        if self.phase == "war_battle":
            if self.attacker_hand.length() == 0 or self.defender_hand.length() == 0:
                # If out of cards, resolve instantly
                winner = "defender" if self.attacker_hand.length() == 0 else "attacker"
                step = {
                    "phase": "war_battle",
                    "winner": winner,
                    "attacker_card": None,
                    "defender_card": None
                }
                self.phase = "normal"
                self.spoils_pile.clear()
                return step
    
            attacker_card = self.attacker_hand.draw()
            logger.info(f"Attacker {self.attacker.name} drew card: {attacker_card.value}")
            defender_card = self.defender_hand.draw()
            logger.info(f"Defender {self.defender.name} drew card: {defender_card.value}")
            self.spoils_pile += [attacker_card, defender_card]
            self.last_attacker_card = attacker_card
            self.last_defender_card = defender_card
            logger.info(f"(WAR) Attacker {self.attacker.name}: {attacker_card.value}, Defender {self.defender.name}: {defender_card.value}")
    
            # Resolve outcome
            if attacker_card.wins(defender_card):
                self.attacker_hand.add_spoils(self.spoils_pile)
                winner = self.attacker
                self.phase = "normal"
                self.spoils_pile = []
            elif defender_card.wins(attacker_card):
                self.defender_hand.add_spoils(self.spoils_pile)
                winner = self.defender
                self.phase = "normal"
                self.spoils_pile = []
            else:
                # Another tie in war, new war begins
                num_cards = min(3, self.attacker_hand.length() - 1, self.defender_hand.length() - 1)
                self.war_cards_left = max(0, num_cards)
                logger.info(f"Double tie! Each puts down {self.war_cards_left} more.")
                if self.war_cards_left > 0:
                    self.phase = "war_face_down"
                # If someone runs out, resolve instantly on next click
    
                winner = None  # war continues
    
            return {
                "phase": "war_battle",
                "winner": winner,
                "attacker_card": attacker_card,
                "defender_card": defender_card,
                "face_downs_remaining": self.war_cards_left
            }
    
        # Otherwise: normal round
        # (reaching here means phase is "normal")
        attacker_card = self.attacker_hand.draw()
        defender_card = self.defender_hand.draw()
        self.last_attacker_card = attacker_card
        self.last_defender_card = defender_card
        logger.info(f"Attacker {self.attacker.name} plays: {attacker_card.value}, Defender {self.defender.name} plays: {defender_card.value}")
        spoils = [attacker_card, defender_card]
        if attacker_card.wins(defender_card):
            self.attacker_hand.add_spoils(spoils)
            return {
                "phase": "normal",
                "winner": self.attacker,  # fix here
                "attacker_card": attacker_card,
                "defender_card": defender_card
            }
        elif defender_card.wins(attacker_card):
            self.defender_hand.add_spoils(spoils)
            return {
                "phase": "normal",
                "winner": self.defender,  # fix here
                "attacker_card": attacker_card,
                "defender_card": defender_card
            }
        else:
            # TIE: prepare for war, start with face-downs on next call(s)
            num_cards = min(3, self.attacker_hand.length() - 1, self.defender_hand.length() - 1)
            self.war_cards_left = max(0, num_cards)
            self.phase = "war_face_down" if self.war_cards_left > 0 else "war_battle"
            self.spoils_pile = spoils.copy()
            logger.info(f"Tie detected! Each puts down {self.war_cards_left} for war.")
            return {
                "phase": "normal",
                "winner": None,
                "attacker_card": attacker_card,
                "defender_card": defender_card,
                "face_downs_remaining": self.war_cards_left
            }

    #Simply for testing purposes. Only next_round is used for UI purposes in the actual game
    def battle(self):
         """Conduct a full game of War
         Returns: 
             attacker if attacker won and defender if defender won"""
         won, winner = self.has_won()
         while not won:
             self.next_round()
             won, winner = self.has_won()
         return winner
     