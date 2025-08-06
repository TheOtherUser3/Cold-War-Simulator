# -*- coding: utf-8 -*-
"""
Created on Sun Nov 17 18:35:17 2024

@author: dawso
"""
import random
import logging

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
        logger.info(f"Drew card: {card.value}")
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
             (True/False, attacker/defender (String))"""
         if self.attacker_hand.is_loss():
            logger.info("Defender has won the war!")
            return (True, "defender")
         elif self.defender_hand.is_loss():
            logger.info("Attacker has won the war!")
            return (True, "attacker")
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
            defender_card = self.defender_hand.draw()
            self.spoils_pile += [attacker_card, defender_card]
            self.last_attacker_card = attacker_card
            self.last_defender_card = defender_card
            logger.info(f"(WAR) Attacker: {attacker_card.value}, Defender: {defender_card.value}")
    
            # Resolve outcome
            if attacker_card.wins(defender_card):
                self.attacker_hand.add_spoils(self.spoils_pile)
                winner = "attacker"
                self.phase = "normal"
                self.spoils_pile = []
            elif defender_card.wins(attacker_card):
                self.defender_hand.add_spoils(self.spoils_pile)
                winner = "defender"
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
        logger.info(f"Attacker plays: {attacker_card.value}, Defender plays: {defender_card.value}")
        spoils = [attacker_card, defender_card]
        if attacker_card.wins(defender_card):
            self.attacker_hand.add_spoils(spoils)
            return {
                "phase": "normal",
                "winner": "attacker",
                "attacker_card": attacker_card,
                "defender_card": defender_card
            }
        elif defender_card.wins(attacker_card):
            self.defender_hand.add_spoils(spoils)
            return {
                "phase": "normal",
                "winner": "defender",
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
             "attacker" if attacker won and "defender" if defender won"""
         won, winner = self.has_won()
         while not won:
             self.next_round()
             won, winner = self.has_won()
         return winner
     