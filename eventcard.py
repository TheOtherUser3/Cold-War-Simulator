"""
Event cards engine for the Cold War game.

What you get here:
- A clean loader for your /event_cards.json
- EventCard / EventEffect classes (dataclasses) you can keep in memory
- EventDeck for random draws with year filtering + no repeats within a game
- A single .apply(gamestate, resolver=...) that executes effects immediately
  and returns a list of any interactions that need player input (targets, quiz choices, etc.)

Minimal integration steps (see bottom of file for snippets):
1) Add 3 tiny helpers to GameState (get_country, get_bloc_countries, adjust_defcon)
2) Instantiate EventDeck once at game start
3) Each Current-Events phase: draw_for_year(year) → show UI → card.apply(...)
4) If .apply(...) returns pending interactions, call your UI/resolver to finish them
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Tuple
import json
import random
import logging

# ---------------------------
# Data Model
# ---------------------------

@dataclass
class EventEffect:
    type: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_json(obj: Dict[str, Any]) -> "EventEffect":
        # Normalize a couple of known typos/variants in your JSON
        if "type:" in obj and "type" not in obj:
            obj["type"] = obj.pop("type:")
        return EventEffect(type=obj.get("type", ""), raw=obj)


@dataclass
class EventCard:
    id: int
    title: str
    description: str
    button: str
    image: Optional[str]
    year: Optional[int]
    start_year: Optional[int]
    end_year: Optional[int]
    effects_text: Optional[str]
    effects: List[EventEffect] = field(default_factory=list)

    @staticmethod
    def from_json(idx: int, obj: Dict[str, Any]) -> "EventCard":
        return EventCard(
            id=idx,
            title=obj.get("title", f"Event #{idx}"),
            description=obj.get("description", ""),
            button=obj.get("button", "OK"),
            image=obj.get("image"),
            year=obj.get("year"),
            start_year=obj.get("start_year"),
            end_year=obj.get("end_year"),
            effects_text=obj.get("effects_text"),
            effects=[EventEffect.from_json(e) for e in obj.get("effects", [])],
        )

    # --- availability window ---
    def in_year(self, year: int) -> bool:
        if self.year is not None:
            return self.year == year
        if self.start_year is not None and self.end_year is not None:
            return self.start_year <= year <= self.end_year
        # If neither is present, consider it always valid
        return True

    # --- effect execution ---
    def apply(
        self,
        gs: Any,
        resolver: Optional[Callable[[str, Dict[str, Any], "EventCard", Any], Any]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> Dict[str, Any]:
        """
        Execute all resolvable effects. For effects that need extra input
        (e.g., choose target, quiz answer, which bloc member moves), we append
        a 'pending' entry and keep going.

        Returns dict with:
          - 'log': list[str] human-readable log lines you can show
          - 'pending': list[dict] interaction requests; each entry includes
                {'kind': <one of 'choose_target'|'quiz'|'choose_bloc_member'>,
                 'effect': <original effect dict>, 'card_id': int}
        """
        L: List[str] = []
        pending: List[Dict[str, Any]] = []
        lg = logger or logging.getLogger("events")

        for eff in self.effects:
            kind = eff.type
            data = eff.raw

            try:
                if kind == "pp":
                    c = _country(gs, data["country"]) ; delta = int(data["delta"]) 
                    c.pp = max(0, c.pp + delta)
                    L.append(f"{c.name}: PP {'+' if delta>=0 else ''}{delta} → {c.pp}")

                elif kind == "bloc_pp":
                    bloc = _normalize_bloc(data["bloc"]) ; delta = int(data["delta"]) 
                    for c in _bloc_countries(gs, bloc):
                        c.pp = max(0, c.pp + delta)
                    L.append(f"{bloc}: all members PP {'+' if delta>=0 else ''}{delta}")

                elif kind == "percent_pp":
                    if "bloc" in data:
                        bloc = _normalize_bloc(data["bloc"]) ; pct = float(data["percent"]) 
                        for c in _bloc_countries(gs, bloc):
                            c.pp = max(0, int(c.pp * (1 + pct)))
                        L.append(f"{bloc}: all members PP × {1+pct:.2f}")
                    else:
                        c = _country(gs, data["country"]) ; pct = float(data["percent"]) 
                        old = c.pp ; c.pp = max(0, int(c.pp * (1 + pct)))
                        L.append(f"{c.name}: PP {old} → {c.pp} ({pct*100:.0f}% ")

                elif kind == "defcon":
                    delta = int(data.get("delta", 0))
                    # Treat as relative, then clamp 1..5 (your rules use 1..5)
                    gs.defcon = max(1, min(5, gs.defcon + delta))
                    L.append(f"DEFCON adjusted by {delta} → {gs.defcon}")

                elif kind in ("arms_race", "space_race"):
                    c = _country(gs, data["country"]) ; delta = int(data.get("delta", 0))
                    attr = "arms_race" if kind == "arms_race" else "space_race"
                    cur = getattr(c, attr)
                    new = max(0, min(4, cur + delta))
                    setattr(c, attr, new)
                    L.append(f"{c.name}: {attr.replace('_',' ').title()} {cur} → {new}")

                elif kind == "gain_space_race_tier":
                    c = _country(gs, data["country"]) ; tier = int(data.get("tier", 0))
                    cur = c.space_race ; new = max(cur, min(4, tier))
                    c.space_race = new
                    L.append(f"{c.name}: Space Race set to ≥{tier} (now {new})")

                elif kind == "arms_race_lock":
                    duration = int(data.get("duration", data.get("duration_rounds", 1)))
                    cur = getattr(gs, "arms_race_lock_remaining", 0)
                    gs.arms_race_lock_remaining = max(cur, duration)
                    L.append(f"Arms Race purchases locked for {duration} round(s)")

                elif kind == "destabilize":
                    # actor/target names vary across cards. Prefer explicit keys.
                    actor_name = data.get("actor") or data.get("country")
                    target_name = data.get("target")
                    if actor_name and target_name:
                        gs.destabilize_die(_country(gs, actor_name), _country(gs, target_name))
                        L.append(f"Destabilize die: {actor_name} → {target_name}")
                    else:
                        pending.append({"kind": "choose_target", "effect": data, "card_id": self.id, "action": "destabilize"})

                elif kind == "espionage" or kind == "free_espionage":
                    actor_name = data.get("actor")
                    target_name = data.get("target")
                    if actor_name and target_name:
                        gs.espionage_die(_country(gs, actor_name), _country(gs, target_name))
                        L.append(f"Espionage die: {actor_name} → {target_name}")
                    else:
                        pending.append({"kind": "choose_target", "effect": data, "card_id": self.id, "action": "espionage"})

                elif kind == "coup":
                    actor_name = data.get("actor") or data.get("country")
                    target_name = data.get("target")
                    if actor_name and target_name:
                        gs.coup_die(_country(gs, actor_name), _country(gs, target_name))
                        L.append(f"Coup die: {actor_name} → {target_name}")
                    else:
                        pending.append({"kind": "choose_target", "effect": data, "card_id": self.id, "action": "coup"})

                elif kind == "classified_documents":
                    actor_name = data.get("actor") or data.get("country")
                    target_name = data.get("target")
                    if actor_name and target_name:
                        gs.classifieddocs_die(_country(gs, actor_name), _country(gs, target_name))
                        L.append(f"Classified Docs die: {actor_name} → {target_name}")
                    else:
                        pending.append({"kind": "choose_target", "effect": data, "card_id": self.id, "action": "classified_docs"})

                elif kind == "war_outcome":
                    actor_name = data.get("actor") or data.get("country")
                    target_name = data.get("target")
                    if actor_name and target_name:
                        gs.waroutcome_die(_country(gs, actor_name), _country(gs, target_name))
                        L.append(f"War Outcome die: {actor_name} → {target_name}")
                    else:
                        pending.append({"kind": "choose_target", "effect": data, "card_id": self.id, "action": "war_outcome"})

                elif kind == "flip_coin_defcon":
                    gs.coin_flip()
                    L.append("DEFCON Coin flip")

                elif kind == "draw_card_defcon":
                    # Draw one random card: Ace (1) lowers, King (13) raises per your JSON
                    rank = random.randint(1, 13)
                    aces_delta = int(data.get("aces_delta", -1))
                    kings_delta = int(data.get("kings_delta", +1))
                    d = aces_delta if rank == 1 else (kings_delta if rank == 13 else 0)
                    if d:
                        gs.defcon = max(1, min(5, gs.defcon + d))
                    L.append(f"Drew rank {rank}; DEFCON {'changed' if d else 'unchanged'} → {gs.defcon}")

                elif kind == "skip_turn":
                    c = _country(gs, data["country"]) ; dur = int(data.get("duration_rounds", 1))
                    setattr(c, "skip_turn_rounds", max(dur, getattr(c, "skip_turn_rounds", 0)))
                    L.append(f"{c.name} will skip {dur} round(s)")

                elif kind == "bloc_member_vote":
                    # Let UI resolve WHICH member moves; we only know from/to blocs
                    pending.append({"kind": "choose_bloc_member", "effect": data, "card_id": self.id, "action": "bloc_member_vote"})

                elif kind == "discount":
                    # e.g., {type:"discount", country:"USA", subject:"arms_race", tier:1, multiplier:0.5}
                    country = data["country"]; subject = data["subject"]; tier = int(data.get("tier", -1))
                    mult = float(data.get("multiplier", 1.0))
                    disc = getattr(gs, "race_discounts", {})
                    disc[(country, subject, tier)] = mult
                    gs.race_discounts = disc
                    L.append(f"Discount set: {country} {subject} tier {tier} ×{mult}")

                elif kind == "quiz":
                    q = {
                        "kind": "quiz",
                        "effect": data,
                        "card_id": self.id,
                        "action": "quiz",
                        "question": data.get("question", "Answer yes or no"),
                    }
                    if resolver:
                        ans = resolver("quiz", data, self, gs)  # expect True for yes, False for no
                    else:
                        ans = None
                    if ans is None:
                        pending.append(q)
                    else:
                        _apply_quiz_branch(gs, data, ans, L)

                else:
                    # Unknown/unimplemented effect
                    L.append(f"(Ignored unknown effect type: {kind})")

            except Exception as e:
                lg.exception(f"Error applying effect {kind} on card {self.title}: {e}")
                L.append(f"[ERROR] Could not apply effect {kind}: {e}")

        return {"log": L, "pending": pending}


# ---------------------------
# Deck & Loader
# ---------------------------

class EventDeck:
    def __init__(self, json_path: str):
        self.cards: List[EventCard] = []
        self._used: set[int] = set()
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for i, obj in enumerate(raw):
            self.cards.append(EventCard.from_json(i, obj))

    def reset(self):
        self._used.clear()

    def available_for_year(self, year: int) -> List[EventCard]:
        return [c for c in self.cards if c.id not in self._used and c.in_year(year)]

    def draw_for_year(self, year: int) -> Optional[EventCard]:
        pool = self.available_for_year(year)
        if not pool:
            return None
        card = random.choice(pool)
        self._used.add(card.id)
        return card

    def put_back(self, card: EventCard) -> None:
        self._used.discard(card.id)


# ---------------------------
# Helpers (do not assume internal GameState methods)
# ---------------------------

def _normalize_bloc(tag: str) -> str:
    """Map JSON tags to your Country.bloc strings."""
    t = tag.lower().strip()
    if t.startswith("nato"):       return "NATO"
    if t.startswith("warsaw"):     return "Warsaw Pact"
    if t.startswith("non"):        return "Non-Aligned"
    return tag  # fallback as-is


def _country(gs: Any, name: str):
    for c in gs.countries:
        if c.name == name:
            return c
    raise KeyError(f"No such country: {name}")


def _bloc_countries(gs: Any, bloc_tag: str):
    tgt = _normalize_bloc(bloc_tag)
    return [c for c in gs.countries if c.bloc == tgt]


def _apply_quiz_branch(gs: Any, data: Dict[str, Any], answered_yes: bool, L: List[str]):
    key = "effects_if_yes" if answered_yes else "effects_if_no"
    for sub in data.get(key, []):
        # Reuse the same executor by making a tiny one-off EventCard
        card = EventCard(
            id=-1, title="(quiz branch)", description="", button="", image=None,
            year=None, start_year=None, end_year=None, effects_text=None,
            effects=[EventEffect.from_json(sub)]
        )
        result = card.apply(gs)
        L.extend(result["log"])  # sub-effects should not emit their own pendings in these cards


# ---------------------------
# Suggested tiny additions to GameState (drop-in)
# ---------------------------
SUGGESTED_GAMESTATE_PATCH = """
# In GameState.__init__ add
self.race_discounts = {}
self.arms_race_lock_remaining = 0

# (optional) helpers

def get_country(self, name: str):
    for c in self.countries:
        if c.name == name: return c
    raise KeyError(f"No such country: {name}")


def get_bloc_countries(self, bloc_tag: str):
    tgt = bloc_tag if bloc_tag in ("NATO", "Warsaw Pact", "Non-Aligned") else (
        "NATO" if bloc_tag.lower().startswith("nato") else (
        "Warsaw Pact" if bloc_tag.lower().startswith("warsaw") else "Non-Aligned"))
    return [c for c in self.countries if c.bloc == tgt]


def adjust_defcon(self, delta: int):
    self.defcon = max(1, min(5, self.defcon + delta))
    return self.defcon
"""

# ---------------------------
# Integration example (copy/paste into your code where you handle Current Events)
# ---------------------------
INTEGRATION_SNIPPET = """
# 1) Create the deck once
from event_engine import EventDeck
self.event_deck = EventDeck("data/event_cards.json")  # path relative to your working dir

# 2) Each time you need a current event for the given game year
card = self.event_deck.draw_for_year(self.year)  # or however you track the year
if card is None:
    # no events left matching this year. You can draw from the full deck as fallback
    card = self.event_deck.draw_for_year(self.year - 1)  # or handle gracefully

# 3) Show the UI (title, description, card.image, and a big button = card.button)
#    When the player clicks, call apply(); provide a resolver to satisfy missing targets

def resolver(kind, effect, card_obj, gs):
    # Kind can be: 'choose_target', 'quiz', 'choose_bloc_member'
    if kind == 'quiz':
        # Wire this to your UI Yes/No; here we just default False
        return False
    if kind == 'choose_target':
        # Example: aim at the opposing superpower by default
        actor = effect.get('actor') or effect.get('country')
        if actor in ('USA', 'United States'):
            return {'actor': actor, 'target': 'USSR'}
        if actor == 'USSR':
            return {'actor': actor, 'target': 'USA'}
        # Fallback: no decision — your UI should let the player click a target country on the map
        return None
    if kind == 'choose_bloc_member':
        # Example: move a random Warsaw member to Non-Aligned
        from_bloc = effect.get('from_bloc', 'Warsaw')
        to_bloc = effect.get('to_bloc', 'Non-Aligned')
        members = gs.get_bloc_countries(from_bloc)
        if not members:
            return None
        chosen = random.choice(members)
        return {'country': chosen.name, 'to_bloc': to_bloc}

result = card.apply(self, resolver=resolver)

# 4) If result['pending'] still has items, prompt the player and re-apply just those items
for p in result['pending']:
    if p['kind'] == 'quiz':
        # ask player; suppose ans is True/False
        ans = True
        # feed the chosen branch
        from event_engine import _apply_quiz_branch  # or expose a public wrapper
        _apply_quiz_branch(self, p['effect'], ans, [])
    elif p['kind'] == 'choose_target':
        # present a country picker; fill in 'actor' (if missing) and 'target'
        pass
    elif p['kind'] == 'choose_bloc_member':
        # present a list of bloc members to move; then:
        info = {'country': 'Poland', 'to_bloc': 'Non-Aligned'}
        c = self.get_country(info['country'])
        c.bloc = info['to_bloc']

# 5) Append result['log'] to your GameState.action_log for a readable audit
self.action_log.extend(result['log'])
"""

if __name__ == "__main__":
    # Minimal manual test (no GameState): just make sure the deck loads and filters
    deck = EventDeck("data/event_cards.json")
    sample = deck.available_for_year(1962)
    print(f"1962 has {len(sample)} available event(s)")
    print(deck.cards[1])
