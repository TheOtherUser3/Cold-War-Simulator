"""Handles the turn based system"""

import logging
import pygame
from models import Country, Bloc
from dice import Dice, DiceManager, DiceFace
from spinner import Spinner, SpinnerManager, OPTIONS
from War import WarManager
from coin import CoinManager, Coin
from quiz import QuizManager
from card import CardDrawManager
from discount import OfferManager


COUP_DIE = Dice([
    DiceFace("DEFCON lowers"),
    DiceFace("Transfer Country"),
    DiceFace("Target Loses 10% PP"),
    DiceFace("Roll Classified Docs"),
    DiceFace("Failed Coup (No Effect)"),
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
    def __init__(self, screen, blocs, countries, currently_playing, max_turns=10):
        self.turn = 1
        self.max_turns = max_turns
        self.defcon = 5
        self.blocs = blocs
        self.countries = countries
        self.victory = None
        self.arms_race_lock = 0 #Cuban Missile Crisis Event Card, nobody can buy for one round, number indicates number of turns, 3 per round, set to 3
        self.currently_playing = currently_playing
        self.action_log = []
        self.screen = screen
        self.spinner_mgr = SpinnerManager(screen, Spinner(OPTIONS))
        self.dice_mgr = DiceManager(screen)
        self.coin_mgr = CoinManager(self.screen)
        self.quiz_mgr = QuizManager(self.screen, self.get_currently_playing)
        self.card_mgr = CardDrawManager(self.screen)
        self.offer_mgr = OfferManager(self.screen)



        # Phases state
        self.espionage_moves = []   # [(country, target_country)]
        self.action_moves = []      # [(country, [(action_type, params)])]
        self.war_moves = []         # [(attacker, defender)]
        self.support_moves = []     # [(supporting_country, supported_country, amount)]
        self.espionage_results = []
    
    def change_defcon(self, delta):
        """Changes defcon by specified amount and checks for game over"""
        logging.info(f"change_defcon called with delta {delta}, current {self.defcon} returned: {max(1, min(5, self.defcon + delta))}")
        self.defcon = max(1, min(5, self.defcon + delta))
        #TO DO: ADD GAME OVER CHECK/UI CALL ONCE THAT IS IMPLEMENTED

    def get_defcon(self):
        logging.info(f"get_defcon called, returned: {self.defcon}")
        return self.defcon
    
    def get_currently_playing(self):
        logging.info(f"get_currently_playing called, returned country {self.currently_playing.name}")
        return self.currently_playing
    
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


    def coin_flip(self):
        """Wrapper function to flip the DEFCON Coin and apply its effects"""
        logging.info("coin_flip: starting DEFCON coin flip")
        def on_result(idx: int, label: str) -> None:
            before = self.defcon
            delta = 1 if idx == 0 else -1     # +1 on RAISE, -1 on LOWER
            after = max(1, min(5, self.defcon + delta))
            logging.info(f"coin_flip: result idx={idx} label='{label}' delta={delta} defcon {before} -> {after}")
            self.defcon = after
        self.coin_mgr.start_flip(Coin.defcon(), on_result=on_result)
    
    
    # --- DICE ---
    
    def coup_die(self, actor, target):
        """actor rolls coup dice on target"""
        logging.info(f"coup_die: start actor={actor.name} target={target.name}")
        def _on_result(idx: int, label: str) -> None:
            logging.info(f"coup_die: result idx={idx} label='{label}'")
            match idx:
                case 0:
                    self.defcon -= 1
                    logging.info(f"coup_die: DEFCON lowered -> {self.defcon}")
                case 1:
                    target.bloc = actor.bloc
                    logging.info(f"coup_die: {target.name} transferred to bloc {actor.bloc.name}")
                case 2:
                    before = target.pp
                    target.pp = int(target.pp * 0.9)
                    logging.info(f"coup_die: {target.name} loses 10% PP {before} -> {target.pp}")
                case 3:
                    logging.info("coup_die: rolling Classified Docs due to result")
                    self.classifieddocs_die(actor, target)
                case 4:
                    logging.info("coup_die: failed coup (no effect)")
                    return
                case 5:
                    actor.war_power += 1
                    logging.info(f"coup_die: {actor.name} +1 War Power -> {actor.war_power}")
        self.dice_mgr.start_roll(
            COUP_DIE,
            on_result=_on_result,
            title="Coup",
            actor_name=actor.name,
            target_name=target.name,
        )
    
    
    def espionage_die(self, actor, target):
        """actor rolls espionage dice on target"""
        logging.info(f"espionage_die: start actor={actor.name} target={target.name}")
        def _on_result(idx: int, label: str) -> None:
            logging.info(f"espionage_die: result idx={idx} label='{label}'")
            match idx:
                case 0:
                    self.defcon -= 1
                    logging.info(f"espionage_die: DEFCON lowered -> {self.defcon}")
                case 1:
                    if target.space_race > actor.space_race:
                        actor.space_race += 1
                        logging.info(f"espionage_die: {actor.name} steals Space Race tier -> {actor.space_race}")
                case 2:
                    if target.arms_race > actor.arms_race:
                        actor.arms_race += 1
                        logging.info(f"espionage_die: {actor.name} steals Arms Race tier -> {actor.arms_race}")
                case 3:
                    self.defcon += 1
                    logging.info(f"espionage_die: DEFCON raised -> {self.defcon}")
                case 4:
                    before_a, before_t = actor.pp, target.pp
                    actor.pp = int(actor.pp + target.pp * 0.10)
                    target.pp = int(target.pp * 0.9)
                    logging.info(f"espionage_die: PP transfer actor {before_a}->{actor.pp} target {before_t}->{target.pp}")
                case 5:
                    logging.info("espionage_die: rolling Classified Docs due to result")
                    self.classifieddocs_die(actor, target)
        self.dice_mgr.start_roll(
            ESPIONAGE_DIE,
            on_result=_on_result,
            title="Espionage",
            actor_name=actor.name,
            target_name=target.name,
        )
    
    
    def destabilize_die(self, actor, target):
        """actor rolls destabilize dice on target"""
        logging.info(f"destabilize_die: start actor={actor.name} target={target.name}")
        def _on_result(idx: int, label: str) -> None:
            logging.info(f"destabilize_die: result idx={idx} label='{label}'")
            match idx:
                case 0:
                    if actor != target:
                        logging.info("destabilize_die: result starts war")
                        self.start_war(actor, target)
                case 1:
                    before = target.war_power
                    target.war_power -= 2
                    logging.info(f"destabilize_die: {target.name} war power {before}->{target.war_power}")
                case 2:
                    logging.info("destabilize_die: guaranteed coup roll")
                    self.coup_die(actor, target)
                case 3:
                    self.defcon -= 1
                    logging.info(f"destabilize_die: DEFCON lowered -> {self.defcon}")
                case 4:
                    logging.info("destabilize_die: guaranteed espionage roll")
                    self.espionage_die(actor, target)
                case 5:
                    before_a, before_t = actor.pp, target.pp
                    actor.pp = int(actor.pp + target.pp * 0.10)
                    target.pp = int(target.pp * 0.9)
                    logging.info(f"destabilize_die: PP transfer actor {before_a}->{actor.pp} target {before_t}->{target.pp}")
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
        logging.info(f"waroutcome_die: start actor={actor.name} target={target.name}")
        def _on_result(idx: int, label: str) -> None:
            logging.info(f"waroutcome_die: result idx={idx} label='{label}'")
            match idx:
                case 0:
                    target.bloc = actor.bloc
                    logging.info(f"waroutcome_die: transfer country -> {target.name} to bloc {actor.bloc.name}")
                case 1:
                    before_a, before_t = actor.pp, target.pp
                    actor.pp = int(actor.pp + target.pp * 0.10)
                    target.pp = int(target.pp * 0.9)
                    logging.info(f"waroutcome_die: reparations extra 10%% actor {before_a}->{actor.pp} target {before_t}->{target.pp}")
                case 2:
                    if target.arms_race > actor.arms_race:
                        actor.arms_race += 1
                        logging.info(f"waroutcome_die: steal Arms Race tier -> {actor.arms_race}")
                case 3:
                    logging.info("waroutcome_die: Imbroglio — negating other war effects")
                    return
                case 4:
                    rep = min(50, target.pp)
                    target.pp -= rep
                    actor.pp += rep
                    logging.info(f"waroutcome_die: war reparations {rep} PP; actor->{actor.pp}, target->{target.pp}")
                case 5:
                    self.defcon -= 1
                    logging.info(f"waroutcome_die: DEFCON lowered -> {self.defcon}")
            # Other benefits/losses of war handled here
            actor.pp += 300
            penalty = min(50, target.pp)
            target.pp -= penalty
            logging.info(f"waroutcome_die: post-war awards actor +300PP, target -{penalty}PP (actor->{actor.pp}, target->{target.pp})")
        self.dice_mgr.start_roll(
            WAROUTCOME_DIE,
            on_result=_on_result,
            title="War Outcome",
            actor_name=actor.name,
            target_name=target.name,
        )
    
    
    def classifieddocs_die(self, actor, target):
        """actor rolls classified docs dice on target"""
        logging.info(f"classifieddocs_die: start actor={actor.name} target={target.name}")
        def _on_result(idx: int, label: str) -> None:
            logging.info(f"classifieddocs_die: result idx={idx} label='{label}'")
            match idx:
                case 0:
                    self.defcon += 1
                    logging.info(f"classifieddocs_die: DEFCON raised -> {self.defcon}")
                case 1:
                    if target.space_race > actor.space_race:
                        actor.space_race += 1
                        logging.info(f"classifieddocs_die: steal Space Race tier -> {actor.space_race}")
                case 2:
                    before = actor.pp
                    actor.pp = int(actor.pp * 1.15)
                    logging.info(f"classifieddocs_die: gain 15% PP {before}->{actor.pp}")
                case 3:
                    before = actor.war_power
                    actor.war_power += 2
                    logging.info(f"classifieddocs_die: +2 War Power {before}->{actor.war_power}")
                case 4:
                    actor.free_war = True
                    logging.info("classifieddocs_die: Free War Cost enabled")
                case 5:
                    logging.info("classifieddocs_die: rolling Destabilize due to result")
                    self.destabilize_die(actor, target)
        self.dice_mgr.start_roll(
            CLASSIFIEDDOCS_DIE,
            on_result=_on_result,
            title="Classified Docs",
            actor_name=actor.name,
            target_name=target.name,
        )
    
    
    # --- SPINNER ---
    
    def coup_spinner(self, actor, target):
        """
        Actor rolls the coup spinner on target country.  Applies all effects after
        """
        logging.info(f"coup_spinner: start actor={actor.name} target={target.name}")
        def _on_result(idx: int, label: str) -> None:
            logging.info(f"coup_spinner: result idx={idx} label='{label}'")
            match idx:
                case 0:  # Failed Coup — Roll Classified Docs Die
                    self.classifieddocs_die(actor, target)
                case 1:  # Failed Coup — Starts War
                    self.start_war(actor, target)
                case 2:  # Successful Coup — Roll Coup + Destabilize
                     self.coup_die(actor, target)
                     self.destabilize_die(actor, target)
                case 3:  # Failed Coup — Pay 10 % extra PP
                    before = actor.pp
                    actor.pp = int(actor.pp * 0.9)
                    logging.info(f"coup_spinner: actor pays 10% {before}->{actor.pp}")
                case 4:  # Failed Coup — Roll Destabilize Die
                    self.destabilize_die(actor, target)
                case 5:  # Failed Coup — Recoup coup cost (100)
                    actor.pp += 100
                    logging.info(f"coup_spinner: actor recoups 100 PP -> {actor.pp}")
                case 6:  # Successful Coup — Roll Coup + Classified Docs
                    self.coup_die(actor, target)
                    self.classifieddocs_die(actor, target)
        self.spinner_mgr.start_spin(
            on_result=_on_result,
            title="Coup Spinner",
            actor_name=actor.name,
            target_name=target.name,
        )
    
    
    # --- QUIZ ---
    
    def quiz_open(
        self,
        question: str,
        correct_is_yes: bool,
        target,  # Country object OR country name string
        *,
        effects_if_correct: str = "",
        effects_if_wrong: str = "",
        on_correct=None,
        on_wrong=None,
        observer_auto_answer: bool | None = None,
        ai_delay_range_ms=(1200, 2600),
    ) -> bool:
        """Open a targeted quiz with uniform behavior.
    
        - Only the target country can answer if it's their turn and not AI.
        - If target is AI, a random answer is chosen after a short delay.
        - If target is a remote human, call `quiz_force_answer(True/False)` when you receive their choice.
        - `on_correct` / `on_wrong` (optional) are executed *after dismissal*.
        """
        if isinstance(target, str):
            logging.info(f"quiz_open: resolving target by name '{target}'")
            target = self.country(target)
    
        logging.info(
            "quiz_open: start question=%r correct_is_yes=%s target=%s effects_if_correct=%r effects_if_wrong=%r"
            % (question, correct_is_yes, getattr(target, 'name', target), effects_if_correct, effects_if_wrong)
        )
    
        def _on_result(selected_yes: bool, correct_yes: bool, is_correct: bool):
            logging.info(
                f"quiz_open: result selected_yes={selected_yes} correct_yes={correct_yes} is_correct={is_correct}"
            )
            if is_correct:
                if callable(on_correct):
                    on_correct()
            else:
                if callable(on_wrong):
                    on_wrong()
    
        return self.quiz_mgr.start_quiz(
            question=question,
            correct_is_yes=correct_is_yes,
            target_country=target,
            on_result=_on_result,
            effects_if_correct=effects_if_correct,
            effects_if_wrong=effects_if_wrong,
            ai_delay_range_ms=ai_delay_range_ms,
            observer_auto_answer=observer_auto_answer,
        )
    
    
    def start_war(self, attacker, defender):
        fonts = (
            pygame.font.SysFont("Segoe UI", 36),
            pygame.font.SysFont("Segoe UI", 24),
            pygame.font.SysFont("Segoe UI", 18),
            pygame.font.SysFont("Segoe UI", 40, bold=True),
        )
        logging.info(f"start_war: attacker={attacker.name} defender={defender.name}")
        #TO DO ADD WAR INITIALIZATION LOGIC + CALL HERE FOR COUNTRY AID
        def on_war_finished(winner):
            logging.info(f"start_war: finished winner={getattr(winner, 'name', winner)}")
            if winner == attacker:
                actor, target = attacker, defender
            else:
                actor, target = defender, attacker
            logging.info(f"start_war: launching waroutcome_die actor={actor.name} target={target.name}")
            self.waroutcome_die(actor, target)
    
        self.war_mgr = WarManager(self.screen, attacker, defender, fonts, on_result=on_war_finished)
    
    def draw_card_defcon(self, aces_delta: int, kings_delta: int):
        def _on(card):
            if card.rank == "A":
                self.change_defcon(aces_delta)
                self.action_log.append("ACE drawn — DEFCON -1")
            elif card.rank == "K":
                self.change_defcon(kings_delta)
                self.action_log.append("KING drawn — DEFCON +1")
            else:
                self.action_log.append(f"{card.rank}{card.suit} drawn — no effect")
        self.card_mgr.start_draw(on_result=_on, title="DEFCON DRAW")
    
    
    def _race_tier_get(self, actor, subject: str) -> int:
        return actor.arms_race if subject == "arms_race" else actor.space_race
    
    def _race_tier_set(self, actor, subject: str, val: int) -> None:
        if subject == "arms_race":
            actor.arms_race = val
        else:
            actor.space_race = val
        
    def offer_race_discount(self, actor, subject: str, discount: float = 0.5,
                            title: str | None = None, question: str | None = None,
                            costs_override: list[int] | None = None) -> bool:
        """
        Offer to buy the *next* tier at a discount. YES is auto-disabled if actor lacks PP or is max tier.
        On accept: deduct PP, +1 tier, append log.
        """
    
        def _on(accepted: bool, price: int) -> None:
            if not accepted:
                return
            # spend and advance
            actor.pp -= price
            new_tier = min(5, self._race_tier_get(actor, subject) + 1)
            self._race_tier_set(actor, subject, new_tier)
            self.action_log.append(
                f"{actor.name} purchased discounted {('Arms' if subject=='arms_race' else 'Space')} Race tier {new_tier} for {price} PP."
            )
    
        return self.offer_mgr.start_offer(
            actor,
            subject,
            mode="discount_next_tier",
            discount=discount,
            title=title,
            question=question,
            costs_override=costs_override,
            on_result=_on,
        )
    
    def offer_race_fixed_to_tier(self, actor, subj: str, target_tier: int, price: int,
                                 title: str | None = None, question: str | None = None) -> bool:
        """
        Offer to pay a fixed price to reach target_tier (jump up if below).
        On accept: deduct PP, set tier = max(current, target_tier) capped at 4, append log.
        """
    
        def _on(accepted: bool, paid: int) -> None:
            if not accepted:
                return
            actor.pp -= paid
            cur = self._race_tier_get(actor, subj)
            new_tier = min(5, max(cur, int(target_tier)))
            self._race_tier_set(actor, subj, new_tier)
            self.action_log.append(
                f"{actor.name} paid {paid} PP to reach {('Arms' if subj=='arms_race' else 'Space')} Race tier {new_tier}."
            )
    
        return self.offer_mgr.start_offer(
            actor,
            subject=subj,
            mode="fixed_purchase_to_tier",
            price=int(price),
            target_tier=int(target_tier),
            title=title,
            question=question,
            on_result=_on,
        )
        
    def country(self, name):
        """To be used externally to extract a country object by name e.g. 'USA' or 'Brazil'"""
        logging.info(f"country() called on {name}")
        return self.countries[name]
    
    
