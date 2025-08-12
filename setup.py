from models import Country, Bloc

def init_countries_and_blocs():
    # Define all blocs
    nato = Bloc("NATO")
    warsaw = Bloc("Warsaw Pact")
    non_aligned = Bloc("Non-Aligned")

    nato_countries = [
        ("USA", 1996), ("Israel", 25), ("Canada", 110), ("West Germany", 200),
        ("Turkey", 39), ("Japan", 235), ("Australia", 103), ("United Kingdom", 518),
        ("France", 435), ("Italy", 195), ("New Zealand", 30), ("South Korea", 28)
    ]

    warsaw_countries = [
        ("USSR", 1310), ("China", 595), ("Poland", 110), ("East Germany", 90),
        ("Czechoslovakia", 63), ("Hungary", 38), ("Romania", 34), ("Bulgaria", 12),
        ("North Korea", 26)
    ]

    non_aligned_countries = [
        ("Honduras", 3), ("Argentina", 42), ("Nicaragua", 3), ("Cuba", 20), ("Brazil", 99),
        ("Venezuela", 42), ("Afghanistan", 26), ("Chile", 24), ("Congo", 4), ("Ethiopia", 11),
        ("Yugoslavia", 35), ("Iran", 35), ("Saudi Arabia", 12), ("Egypt", 32), ("Pakistan", 40),
        ("India", 252), ("Vietnam", 42), ("Indonesia", 76), ("Finland", 62), ("Spain", 76),
        ("El Salvador", 4), ("Mexico", 82), ("Syria", 11), ("Colombia", 28), ("Ghana", 7),
        ("Guatemala", 7), ("Liberia", 3)
    ]

    # Use dicts for countries and blocs
    country_dict = {}
    bloc_dict = {"NATO": nato, "Warsaw Pact": warsaw, "Non-Aligned": non_aligned}

    for name, pp in nato_countries:
        c = Country(name, "NATO", pp)
        nato.add_country(c)
        country_dict[name] = c

    for name, pp in warsaw_countries:
        c = Country(name, "Warsaw Pact", pp)
        warsaw.add_country(c)
        country_dict[name] = c

    for name, pp in non_aligned_countries:
        c = Country(name, "Non-Aligned", pp)
        non_aligned.add_country(c)
        country_dict[name] = c

    return bloc_dict, country_dict

