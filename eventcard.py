import json
from typing import List, Optional, Dict, Any

class EventEffect:
    def __init__(self, effect_type: str, **kwargs):
        self.type = effect_type
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"<Effect type={self.type} {self.__dict__}>"

class EventCard:
    def __init__(self, data: Dict[str, Any]):
        self.title = data.get("title")
        self.year = data.get("year") or data.get("start_year")
        self.end_year = data.get("end_year")
        self.description = data.get("description")
        self.effects = [EventEffect(**effect) for effect in data.get("effects", [])]
        self.effects_text = data.get("effects_text")
        self.button = data.get("button")
        self.image = data.get("image")

    def __repr__(self):
        return f"<EventCard '{self.title}' ({self.year})>"


def load_event_cards(filename: str) -> List[EventCard]:
    with open(filename, encoding='utf-8') as f:
        data = json.load(f)
    return [EventCard(card) for card in data]

# Example usage:
if __name__ == "__main__":
    event_cards = load_event_cards("event_cards.json")
    for card in event_cards:
        print(card)
        for eff in card.effects:
            print("   ", eff)
