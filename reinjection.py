"""Barèmes de réinjection du bénéfice (parts "local" et "up").

Source unique, utilisée par le bot (trader.py) et affichée par l'API (page Grille).
Chaque barème est une liste (seuil, taux %) : le premier seuil strictement
supérieur au bénéfice donne le taux ; au-delà du dernier seuil, taux par défaut.
Attention : seuils en valeur absolue, quelle que soit la devise de cotation.
"""

BAREME_LOCAL = [(5, 1000), (10, 500), (15, 300), (25, 200), (40, 150), (60, 100)]
DEFAUT_LOCAL = 50

BAREME_UP = [(10, 100), (15, 50), (25, 30), (40, 20), (60, 15)]
DEFAUT_UP = 10


def _taux(bareme, defaut, benef):
    for seuil, taux in bareme:
        if benef < seuil:
            return taux
    return defaut


def taux_local(benef):
    """Taux (%) de la part "local" en fonction du bénéfice à redistribuer."""
    return _taux(BAREME_LOCAL, DEFAUT_LOCAL, benef)


def taux_up(benef):
    """Taux (%) de la part "up" en fonction du bénéfice à redistribuer."""
    return _taux(BAREME_UP, DEFAUT_UP, benef)


def repartir(benefice, parts):
    """Répartit chaque part réinjectée entre bénéfice et capital.

    Les 100 % du bénéfice sont attribués aux parts dans l'ordre donné
    (local, puis up, puis down) ; ce qui dépasse vient du capital.

    parts : liste de (nom, montant) dans l'ordre de priorité.
    Returns:
        dict {nom: (montant venant du bénéfice, montant venant du capital)}.
    """
    reste = max(float(benefice), 0.0)
    resultat = {}
    for nom, montant in parts:
        montant = max(float(montant), 0.0)
        du_benefice = min(montant, reste)
        reste -= du_benefice
        resultat[nom] = (du_benefice, montant - du_benefice)
    return resultat
