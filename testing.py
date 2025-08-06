import logging
from models import Country, Bloc
from gamestate import GameState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('game.log'),
        logging.StreamHandler()
    ]
)

import pytest

@pytest.fixture
def countries():
    usa = Country("United States", "NATO", 1000)
    france = Country("France", "NATO", 500)
    return usa, france

@pytest.fixture
def game(countries):
    usa, france = countries
    return GameState([], [usa, france])

def test_aid_normal(game, countries):
    usa, france = countries
    result = game.action_aid(usa, france, 100)
    assert result == True
    assert usa.pp == 900           # Immediate deduction
    assert france.pp == 500        # No immediate gain
    assert france.pending_pp == 100

    # Simulate end of turn
    france.apply_pending_pp()
    assert france.pp == 600        # Now the gain is applied
    assert france.pending_pp == 0

def test_aid_over_10_percent(game, countries):
    usa, france = countries
    result = game.action_aid(usa, france, 200)   # 10% of 1000 = 100 max
    assert result == True
    assert usa.pp == 900
    assert france.pp == 500
    assert france.pending_pp == 100

    france.apply_pending_pp()
    assert france.pp == 600
    assert france.pending_pp == 0

def test_aid_negative_amount(game, countries):
    usa, france = countries
    result = game.action_aid(usa, france, -50)
    assert result == False
    assert usa.pp == 1000
    assert france.pp == 500
    assert france.pending_pp == 0

def test_aid_to_self(game, countries):
    usa, _ = countries
    result = game.action_aid(usa, usa, 50)
    assert result == False
    assert usa.pp == 1000
    assert usa.pending_pp == 0

def test_aid_zero(game, countries):
    usa, france = countries
    result = game.action_aid(usa, france, 0)
    assert result == False
    assert usa.pp == 1000
    assert france.pp == 500
    assert france.pending_pp == 0

def test_purchase_arms_tier_success(game, countries):
    usa, france = countries
    usa.pp = 1000
    usa.arms_race = 0
    result = game.action_purchase_race_tier(usa, "arms")
    assert result == True
    assert usa.pp == 700
    assert usa.arms_race == 1

def test_purchase_space_tier_insufficient_pp(game, countries):
    usa, france = countries
    usa.pp = 100
    result = game.action_purchase_race_tier(usa, "space")
    assert result == False
    assert usa.pp == 100
    assert usa.space_race == 0

def test_purchase_arms_tier_maxed_out(game, countries):
    usa, france = countries
    usa.pp = 5000
    usa.arms_race = 4
    result = game.action_purchase_race_tier(usa, "arms")
    assert result == False
    assert usa.pp == 5000
    assert usa.arms_race == 4

def test_bolster_normal(game, countries):
    usa, france = countries
    usa.pp = 1000
    france.pp = 500

    # USA is superpower: invests 75% of 1000 = 750, gets 30% return = 225, total reward = 975
    result = game.action_bolster(usa)
    assert result == True
    assert usa.pp == 250
    assert usa.pending_bolster_reward == 975

    # France is not superpower: invests 50% of 500 = 250, gets 30% return = 75, total reward = 325
    result = game.action_bolster(france)
    assert result == True
    assert france.pp == 250
    assert france.pending_bolster_reward == 325

def test_bolster_low_pp(game, countries):
    usa, france = countries
    usa.pp = 40
    france.pp = 50

    # USA: invests 75% of 40 = 30, gets 80% return = 24, total reward = 54
    result = game.action_bolster(usa)
    assert result == True
    assert usa.pp == 10
    assert usa.pending_bolster_reward == 54

    # France: invests 50% of 50 = 25, gets 80% return = 20, total reward = 45
    result = game.action_bolster(france)
    assert result == True
    assert france.pp == 25
    assert france.pending_bolster_reward == 45

def test_bolster_zero_invest(game, countries):
    usa, france = countries
    usa.pp = 0
    result = game.action_bolster(usa)
    assert result == True
    assert usa.pp == 0
    assert usa.pending_bolster_reward == 0

def test_bolster_multiple_turns(game, countries):
    usa, _ = countries
    usa.pp = 1000
    game.action_bolster(usa)
    # Simulate start of next turn
    reward = usa.pending_bolster_reward
    usa.pending_bolster_reward = 0
    usa.pp += reward
    assert usa.pp == 250 + 975  # after first turn, pp=250; after reward, pp=1225

    # Now bolster again
    game.action_bolster(usa)
    # Should invest 918 (75% of 1225=918.75->918), get 30% = 275.4, round up, reward=1194
    assert usa.pp == 1225 - 918
    assert usa.pending_bolster_reward == 1194
