"""Handles the turn based system"""

import logging
import pygame
from models import Country, Bloc
from dice import Dice, DiceManager, DiceFace
from spinner import Spinner, SpinnerManager, OPTIONS
from War import WarManager
from coin import CoinManager, Coin
from quiz import QuizManager

COUP_DIE = Dice([
    DiceFace("DEFCON lowers"),
    DiceFace("Transfer Country"),
    DiceFace("Target Loses 10% PP"),
    DiceFace("Roll Classified Docs"),
    DiceFace("Failed Coup"),
    DiceFace("+1 War Power"),
])

ESPIONAGE_DIE = Dice([
    DiceFace("DEFCON lowers"),
    DiceFace("Steal Space Race"),
    DiceFace("Steal Arms Race"),
    DiceFace("DEFCON raises"),
    DiceFace("Steal 10% PP"),
    DiceFace("Roll Classified Docs"),
])

DESTABILIZE_DIE = Dice([
    DiceFace("Starts War"),
    DiceFace("Remove 2 War Power"),
    DiceFace("Guaranteed Coup"), #on target country, roll coup dice
    DiceFace("DEFCON lowers"),
    DiceFace("Guaranteed Espionage"), #On target country, roll espionage dice
    DiceFace("Steal 10% PP"),
])

WAROUTCOME_DIE = Dice([
    DiceFace("Transfer Country"), #To winner's bloc
    DiceFace("Pay Extra 10% PP"), #10% of current PP, on top of other losses
    DiceFace("Steal Arms Race"), 
    DiceFace("Imbroglio (War Effects Negated)"), #No winner or loser regardless of victory, negates outcome benefits/losses
    DiceFace("War Reparations"), #Loser pays 
    DiceFace("DEFCON lowers"),
])

CLASSIFIEDDOCS_DIE = Dice([
    DiceFace("DEFCON raises"),
    DiceFace("Steal Space Race"),
    DiceFace("Gain 15% PP"),
    DiceFace("+2 War Power"),
    DiceFace("Free War Cost"),
    DiceFace("Destabilize"),
])

class GameState:
    def __init__(self, screen, blocs, countries, max_turns=10):
        self.turn = 1
        self.max_turns = max_turns
        self.defcon = 5
        self.blocs = blocs
        self.countries = countries
        self.victory = None
        self.action_log = []
        self.screen = screen
        self.spinner_mgr = SpinnerManager(screen, Spinner(OPTIONS))
        self.dice_mgr = DiceManager(screen)
        self.coin_mgr = CoinManager(self.screen)


        # Phases state
        self.espionage_moves = []   # [(country, target_country)]
        self.action_moves = []      # [(country, [(action_type, params)])]
        self.war_moves = []         # [(attacker, defender)]
        self.support_moves = []     # [(supporting_country, supported_country, amount)]
        self.espionage_results = []

    def run_bloc_turn(self, bloc):
        print(f"\n=== {bloc.name} Phase ===")
        self.collect_espionage_choices(bloc)
        self.collect_action_choices(bloc)
        self.resolve_espionage_phase()
        self.resolve_action_phase()
        self.collect_war_support_choices(bloc)
        self.resolve_war_phase()
        self.handle_war_spoils()
        self.end_of_bloc_cleanup()

    def resolve_war_phase(self):
        # Actually resolve all wars, considering support
        # Populate self.war_moves as needed
        pass

    def end_of_bloc_cleanup(self):
        # Reset phase lists, update logs, check for endgame, etc.
        self.espionage_moves = []
        self.action_moves = []
        self.war_moves = []
        self.support_moves = []
        self.espionage_results = []

    def next_turn(self):
        self.turn += 1
        self.current_bloc_idx = 0
        # Optionally update DEFCON, log turn, etc.

    def is_game_over(self):
        return self.defcon <= 1 or self.turn > self.max_turns or self.victory

    def play_full_turn(self):
        for bloc in self.blocs:
            self.run_bloc_turn(bloc)
        self.next_turn()
    
    def action_aid(self, actor, target, amount):
        """
        Actor donates PP to target, up to 10% of actor's PP.
        
        Params:
            actor (Country) - Country doing the donating
            target (Country) - Country being donated to
            amount (int) - amount of PP to donate
            
        Returns:
            False - if they try to donate to themselves or put a negative number, or if 
                they attempt to donate more than their pending pp would allow
            True - if donation is successful
        """
        #Cannot donate aid to oneself
        if actor == target:
            logging.warning(f"{actor.name} cannot donate aid to themselves.")
            return False

        #Amount must be positive
        if amount <= 0:
            logging.warning(f"Aid amount must be positive. Attempted: {amount}")
            return False

        #Amount cannot be more than 10% of pp, adjust downwards if it is
        max_aid = int(actor.pp * 0.1)
        if amount > max_aid:
            logging.info(f"{actor.name} attempted to donate more than 10% of their current PP ({max_aid}). Adjusted donation to {max_aid}.")
            amount = max_aid
        
        #Apply changes and log
        actor.subtract_pp(amount)
        target.add_pending_pp(amount)

        log_msg = f"{actor.name} donated {amount} PP to {target.name}. (New PP: {actor.name}: {actor.pp}, {target.name}: {target.pp})"
        logging.info(log_msg)
        self.action_log.append(log_msg)
        return True
    
    def action_purchase_race_tier(self, actor, race_type):
        """
        Attempt to purchase the next available tier in the chosen race for the actor.
        
        params:
            actor (Country) - the country purchasing
            race_type (str) - Either "arms" or "space"
            
        returns:
            True if successful, False otherwise
        """
        assert race_type in ("arms", "space"), "Invalid race type."
        
        # Determine current tier
        if race_type == "arms":
            current_tier = actor.arms_race
        else:
            current_tier = actor.space_race
    
        # Max 4 tiers
        if current_tier >= 4:
            logging.warning(f"{actor.name} has already reached the max {race_type} race tier.")
            return False
    
        # Tier costs by index (0-based)
        tier_costs = [300, 900, 1600, 2000]
        next_cost = tier_costs[current_tier]
    
        if actor.pp < next_cost:
            logging.warning(f"{actor.name} does not have enough PP ({actor.pp}) to buy tier {current_tier + 1} in {race_type} race (needs {next_cost}).")
            return False
    
        actor.pp -= next_cost
    
        # Advance tier
        if race_type == "arms":
            actor.arms_race += 1
        else:
            actor.space_race += 1
    
        log_msg = f"{actor.name} purchased tier {current_tier + 1} of the {race_type.capitalize()} Race for {next_cost} PP. New {race_type} tier: {current_tier + 1}."
        logging.info(log_msg)
        self.action_log += log_msg
        return True

    def action_bolster(self, actor):
        """
        Actor invests a portion of their PP to receive a reward next turn.
        US/USSR: invest 75%, all others 50%.
        If PP before bolster is <= 50, return is 80%; else, 30%.
        Investment PP is spent immediately, reward is pending.
        
        Returns true if successful otherwise false
        """
        is_superpower = actor.name in {"United States", "USSR"}
        invest_ratio = 0.75 if is_superpower else 0.5
        invest_amount = int(actor.pp * invest_ratio)
    
        # Determine reward rate based on PP *before* deduction
        if actor.pp <= 50:
            reward = int(invest_amount * 0.8 + 0.999) + invest_amount  # 80% return, round up
        else:
            reward = int(invest_amount * 0.3 + 0.999) + invest_amount # 30% return, round up
    
        actor.pp -= invest_amount
        actor.pending_bolster_reward = reward
        
        log_msg = f"{actor.name} invested {invest_amount} PP in economic activity and will receive {reward} PP at the start of their next turn."
        logging.info(log_msg)
        self.action_log += log_msg
        return True

    def coup_die(self, actor, target):
        """actor rolls coup dice on target"""
        def _on_result(idx: int, label: str) -> None:
            match idx:
                case 0:
                    self.defcon -= 1
                case 1:  
                    target.bloc = actor.bloc
                case 2:  
                    target.pp = int(target.pp* 0.9)
                case 3:  
                    self.classifieddocs_die(actor, target)
                case 4:  
                    return #failed coup after successful coup, no effect
                case 5:  
                    actor.war_power += 1

        self.dice_mgr.start_roll(
            COUP_DIE,
            on_result=_on_result,
            title="Coup",
            actor_name=actor.name,
            target_name=target.name,
        )
    
    def espionage_die(self, actor, target):
        """actor rolls espionage dice on target"""
        def _on_result(idx: int, label: str) -> None:
            match idx:
                case 0:
                    self.defcon -= 1
                case 1:  
                    if target.space_race > actor.space_race:
                        actor.space_race += 1
                case 2:  
                    if target.arms_race > actor.arms_race:
                        actor.arms_race += 1
                case 3:  
                    self.defcon += 1
                case 4:  
                    actor.pp = int(actor.pp + target.pp*0.10)
                    target.pp = int(target.pp* 0.9)
                case 5:  
                    self.classifieddocs_die(actor,target)

        self.dice_mgr.start_roll(
            ESPIONAGE_DIE,
            on_result=_on_result,
            title="Espionage",
            actor_name=actor.name,
            target_name=target.name,
        )
            
    def destabilize_die(self, actor, target):
        """actor rolls destabilize dice on target"""
        def _on_result(idx: int, label: str) -> None:
            match idx:
                case 0:
                    self.start_war(actor, target)
                case 1:  
                    target.war_power -= 2
                case 2:  
                    self.coup_die(actor, target)
                case 3:  
                    self.defcon -= 1
                case 4:  
                    self.espionage_die(actor, target)
                case 5:  
                    actor.pp = int(actor.pp + target.pp*0.10)
                    target.pp = int(target.pp* 0.9)

        self.dice_mgr.start_roll(
            DESTABILIZE_DIE,
            on_result=_on_result,
            title="Destabilize",
            actor_name=actor.name,
            target_name=target.name,
        )
    
    def waroutcome_die(self, actor, target):
        """actor rolls destabilize dice on target
        Since this always rolls after a war, benefits and losses of war are applied here to the winner and loser"""
        def _on_result(idx: int, label: str) -> None:
            match idx:
                case 0:
                    target.bloc = actor.bloc
                case 1:  
                    actor.pp = int(actor.pp + target.pp*0.10)
                    target.pp = int(target.pp* 0.9)
                case 2:  
                    if target.arms_race > actor.arms_race:
                        actor.arms_race += 1
                case 3:  
                    #imbroglio roll means no winner or loser, regardless of war outcome.  All rewards/losses negated
                    return
                case 4:  
                    reperations = min(50, target.pp)
                    target.pp -= reperations
                    actor.pp += reperations
                case 5:  
                    self.defcon -= 1
            #Other benefits/losses of war handled here
            actor.pp += 300
            penalty = min(50, target.pp)
            target.pp -= penalty
                
        self.dice_mgr.start_roll(
            WAROUTCOME_DIE,
            on_result=_on_result,
            title="War Outcome",
            actor_name=actor.name,
            target_name=target.name,
        )

    
    def classifieddocs_die(self, actor, target):
        """actor rolls classified docs dice on target"""
        def _on_result(idx: int, label: str) -> None:
            match idx:
                case 0:
                    self.defcon += 1
                case 1:  
                    if target.space_race > actor.space_race:
                        actor.space_race += 1
                case 2:  
                    actor.pp = int(actor.pp * 1.15)
                case 3:  
                    actor.war_power += 2
                case 4:  
                    actor.free_war = True
                case 5:  
                    self.destabilize_die(actor, target)

        self.dice_mgr.start_roll(
            CLASSIFIEDDOCS_DIE,
            on_result=_on_result,
            title="Classified Docs",
            actor_name=actor.name,
            target_name=target.name,
        )
        
    def coup_spinner(self, actor, target):
        """
        Actor rolls the coup spinner on target country.  Applies all effects after
        
        Returns true if successful otherwise false
        """
        
        def _on_result(idx: int, label: str) -> None:
            match idx:
                case 0:  # Failed Coup — Roll Classified Docs Die
                    self.classifieddocs_die(actor, target)
                case 1:  # Failed Coup — Starts War
                    self.start_war(actor, target)
                case 2:  # Successful Coup — Roll Coup + Destabilize
                     self.coup_die(actor, target)
                     self.destabilize_die(actor, target)
                case 3:  # Failed Coup — Pay 10 % extra PP
                    actor.pp = int(actor.pp * 0.9)
                case 4:  # Failed Coup — Roll Destabilize Die
                    self.destabilize_die(actor, target)
                case 5:  # Failed Coup — Recoup coup cost (100)
                    actor.pp += 100
                case 6:  # Successful Coup — Roll Coup + Classified Docs
                    self.coup_die(actor, target)
                    self.classifieddocs_die(actor, target)

        self.spinner_mgr.start_spin(
            on_result=_on_result,
            title="Coup Spinner",
            actor_name=actor.name,
            target_name=target.name,
        )
    
    def start_war(self, attacker, defender):
        fonts = (
            pygame.font.SysFont("Segoe UI", 36),
            pygame.font.SysFont("Segoe UI", 24),
            pygame.font.SysFont("Segoe UI", 18),
            pygame.font.SysFont("Segoe UI", 40, bold=True),
        )
        # TO DO: ADD CALL TO INITIALIZE WAR HERE BY GIVING COUNTRIES OPTION TO DONATE PP
        def on_war_finished(winner):
            if winner == attacker:
                actor, target = attacker, defender
            else:
                actor, target = defender, attacker
            # Start war outcome die roll with winner/loser
            self.waroutcome_die(actor, target)
    
        self.war_mgr = WarManager(self.screen, attacker, defender, fonts, on_result=on_war_finished)
    
    def coin_flip(self):
        """Wrapper function to flip the DEFCON Coin and apply its effects"""
        def on_result(idx: int, label: str) -> None:
            delta = 1 if idx == 0 else -1     # +1 on RAISE, -1 on LOWER
            self.defcon = max(1, min(5, self.defcon + delta))  # don't let over 5 or under 1
        self.coin_mgr.start_flip(Coin.defcon(), on_result=on_result)
            
    def country(self, name):
        """To be used externally to extract a country object by name e.g. 'USA' or 'Brazil'"""
        return self.countries[name]
    
    
