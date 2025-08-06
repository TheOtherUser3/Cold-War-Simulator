# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:29:33 2024

@author: dawso
"""

from Card import Card
import random

class Hand:
    def __init__(self, length, deck):
        self.cards = []
        self.spoils = []
        for i in range(length):
            if len(deck) == 0:
                [[deck.append(i) for i in range(13)] for j in range(4)]
                random.shuffle(deck)
            self.add(deck.pop())
        #max length determined by the strength of a country or how much support it recieves
        self.length = length
        
    def add(self, value):
        self.cards.append(Card(value, str(value) + ".png"))
    
    def __repr__(self):
        s = "["
        for i in range(len(self.cards) - 1):
            s += str(self.cards[i].value) + ", "
        s += str(self.cards[-1].value)
        s += "]"
        return s
    
    def is_loss(self):
        if len(self.cards) + len(self.spoils) == 0:
            return True
        return False
    
    def check_empty(self):
        if len(self.cards) == 0:
            random.shuffle(self.spoils)
            self.cards = self.spoils
            self.spoils = []
            
        