"""Country and Bloc Classes"""

class Country:
    def __init__(self, name, bloc_name, pp):
        self.name = name
        self.bloc = bloc_name  # 'NATO', 'Warsaw Pact', or 'Non-Aligned'
        self.pp = pp
        self.pending_pp = 0 # To be applied at end of turn
        self.arms_race = 0  # 0-4
        self.space_race = 0  # 0-4
        self.pending_bolster_reward = 0   # To be applied at start of next turn
        self.war_power = 15   
        self.free_war = False
        self.is_ai = False #Whether AI or self/another player is playing

    def __repr__(self):
        return f"<Country {self.name} ({self.bloc}) PP:{self.pp}>"
    
    def add_pending_pp(self, amount):
        """Add to pending PP (cannot be used until end of turn)."""
        self.pending_pp += amount

    def apply_pending_pp(self):
        """Apply pending PP to current PP."""
        self.pp += self.pending_pp
        self.pending_pp = 0
        
    def subtract_pp(self, amount):
        """Subtracts amount pp from current pp.
        
        Params:
            amount (int) - amount to subtract
            
        Returns:
            True - successful
            False - subtracting would cause current pp to fall below 0
        """
        if self.pp - amount < 0:
            return False
        self.pp -= amount
        return True
    
class Bloc:
    def __init__(self, name):
        self.name = name
        self.countries = []

    def add_country(self, country):
        self.countries.append(country)

    def __repr__(self):
        return f"<Bloc {self.name} ({len(self.countries)} countries)>"
