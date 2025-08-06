# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:20:31 2024

@author: dawso
"""

class Card:
    def __init__(self, value, image):
        self.image = image
        self.value = value
        
    def ties(self, other):
        return self.value == other.value
    
    def wins(self, other):
        return self.value > other.value