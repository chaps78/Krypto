"""Mise en forme des messages Telegram.

Ces fonctions sont appelées au milieu du traitement des ordres : une erreur de
mise en forme ne doit jamais interrompre le trading. Chaque message est donc
construit via sur(), qui renvoie un texte de repli en cas de problème.
"""


def sur(construire, repli):
    """Renvoie construire(), ou le texte repli si la mise en forme échoue."""
    try:
        return construire()
    except Exception as inst:
        print("messages : mise en forme impossible : " + str(inst))
        return repli


def _milliers(texte):
    """1234567.5 -> '1 234 567.5' (espace comme séparateur de milliers)."""
    entier, _, decimales = texte.partition(".")
    signe = "-" if entier.startswith("-") else ""
    entier = entier.lstrip("-")
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    return signe + " ".join(groupes) + ("." + decimales if decimales else "")


def quantite(x):
    """Quantité lisible : entière au-delà de 1000, sinon jusqu'à 8 décimales."""
    x = float(x)
    if abs(x) >= 1000:
        return _milliers("%.0f" % x)
    return _milliers(("%.8f" % x).rstrip("0").rstrip("."))


def montant(x):
    """Montant en devise : 2 décimales, ou plus pour les très petites valeurs."""
    x = float(x)
    if abs(x) >= 1 or x == 0:
        return _milliers("%.2f" % x)
    return ("%.8f" % x).rstrip("0").rstrip(".")
