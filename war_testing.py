import pytest
import random
from War import Card, Hand, War

def test_card_comparison():
    c5 = Card(5)
    c8 = Card(8)
    assert c8.wins(c5)
    assert not c5.wins(c8)

def test_hand_add_and_repr():
    deck = [i for i in range(13)] * 4
    h = Hand(5, deck)
    assert len(h.cards) == 5
    h.add(7)
    assert h.cards[-1].value == 7
    s = repr(h)
    assert "[" in s and "]" in s

def test_hand_draw_and_empty():
    deck = [i for i in range(13)] * 4
    h = Hand(2, deck)
    first = h.draw()
    assert isinstance(first, Card)
    second = h.draw()
    assert isinstance(second, Card)
    # After 2 draws, hand is empty (if no spoils)
    assert h.is_loss()
    # Add spoils, then draw again to check reshuffle
    h.add_spoils([Card(1), Card(2)])
    h.check_empty()
    assert len(h.cards) == 2

def test_hand_length():
    deck = [i for i in range(13)] * 4
    h = Hand(4, deck)
    h.add_spoils([Card(1)])
    assert h.length() == 5
    h.draw()
    assert h.length() == 4

def test_hand_draw_num():
    deck = [i for i in range(13)] * 4
    h = Hand(5, deck)
    drawn = h.draw_num(2)
    print(drawn)
    assert len(drawn) == 2
    assert all(isinstance(card, Card) for card in drawn)

def test_war_basic_victory():
    # Attacker is much stronger
    war = War(15, 1)
    # Run until someone wins
    while True:
        result = war.next_round()
        if "winner" in result and result["winner"] in ["attacker", "defender"]:
            break
    assert result["winner"] in ["attacker", "defender"]

def test_war_tie_break(monkeypatch):
    # Disable shuffling for deterministic order
    monkeypatch.setattr(random, "shuffle", lambda x: None)

    war = War(3, 3)

    # Overwrite the last cards so the first draw is a tie (value 7 each)
    war.attacker_hand.cards = [Card(3), Card(2), Card(7)]
    war.defender_hand.cards = [Card(5), Card(1), Card(7)]

    found_tie = False
    for _ in range(10):                      # should tie in the 1st call
        result = war.next_round()
        if result["phase"] == "war_face_down":
            found_tie = True
        if "winner" in result and result["winner"] in ["attacker", "defender"]:
            break
    assert found_tie, "Expected a tie / war sequence but none occurred"
    assert result["winner"] in ["attacker", "defender"]

def test_war_next_round_and_has_won():
    war = War(2, 2)
    result = war.next_round()
    assert isinstance(result, dict)
    assert "phase" in result
    # Play until win
    for _ in range(10):
        status, winner = war.has_won()
        if status:
            assert winner in ["attacker", "defender"]
            break
        war.next_round()

def test_recursive_war_with_7_cards_each(monkeypatch):
    """
    Tests a recursive war scenario with 7 cards per player,
    engineered to force two ties so both players have only two cards left for the final war.
    """
    monkeypatch.setattr(random, "shuffle", lambda x: None)
    war = War(attacker_length=7, defender_length=7)

    war.attacker_hand.cards = [
        Card(8),   # First play (tie)
        Card(9),   # face down
        Card(2),   # face-down 
        Card(4),   # face-down
        Card(7),   # play (tie)
        Card(5),   # face-down 
        Card(10),  # final play (win)
    ]
    war.defender_hand.cards = [
        Card(8),   # first play (tie)
        Card(6),   # face down
        Card(1),   # face-down 
        Card(12),  # face-down 
        Card(7),   # play (tie)
        Card(0),   # face-down 
        Card(5),   # final play (loss)
    ]
    winner = None
    for _ in range(30):
        result = war.next_round()
        if "winner" in result and result["winner"] is not None:
            winner = result["winner"]
            break
    assert winner == "attacker"

def test_game_restarts_on_simultaneous_tie(monkeypatch):
    call_count = {"count": 0}
    original_next_round = War.next_round

    def counting_next_round(self):
        call_count["count"] += 1
        return original_next_round(self)

    # Monkeypatch next_round to count calls
    monkeypatch.setattr(War, "next_round", counting_next_round)
    monkeypatch.setattr(random, "shuffle", lambda x: None)

    war = War(attacker_length=2, defender_length=2)
    war.attacker_hand.cards = [Card(7), Card(5)]
    war.defender_hand.cards = [Card(7), Card(5)]

    # Run rounds until a winner is declared
    winner = None
    for _ in range(10):
        result = war.next_round()
        if "winner" in result and result["winner"] in ["attacker", "defender"]:
            winner = result["winner"]
            break

    assert call_count["count"] >= 2, f"Battle did not restart as expected (only {call_count['count']} rounds)"
    assert winner in ("attacker", "defender")

# Additional test: test war step-by-step
def test_stepwise_war_phases(monkeypatch):
    monkeypatch.setattr(random, "shuffle", lambda x: None)

    war = War(5, 5)

    # Arrange so last element equals (first draw is tie = 6)
    war.attacker_hand.cards = [Card(9), Card(4), Card(3), Card(8), Card(6)]
    war.defender_hand.cards = [Card(7), Card(5), Card(2), Card(1), Card(6)]

    # Initial round: tie
    result = war.next_round()
    assert result["phase"] == "normal"
    assert result["winner"] is None
    assert war.phase == "war_face_down"

    # Place three face-down cards
    for _ in range(3):
        result = war.next_round()
        assert result["phase"] == "war_face_down"

    # Now battle card
    result = war.next_round()
    assert result["phase"] == "war_battle"
    # keep stepping until somebody wins
    for _ in range(10):
        if result.get("winner") in ("attacker", "defender"):
            break
        result = war.next_round()
    assert result["winner"] in ("attacker", "defender")
