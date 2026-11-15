"""Translation (étape 4), consigne 1 : détection des paliers sources. Fonctions pures.

Quand le prix s'est durablement éloigné de paliers bien garnis, ces paliers
pourront céder du capital à la zone du prix (consigne 2, plus tard). Ici, on
ne fait que les repérer ; aucun accès à Binance ni à la base.

Définitions :
    palier courant : dernier palier exécuté (ordre limite), ID ;
    D(S)           = |S − ID|, distance en nombre de paliers ;
    chronomètre    : date à laquelle D(S) est devenu ≥ distance (6), remis à
                     zéro (None) dès que D(S) repasse sous la distance ;
    source éligible : D(S) ≥ distance, chronomètre ≥ durée (48 h) et
                     gain(S) > gain minimal (4,5 €), gain(S) = bet(S) × g(S).
"""
from datetime import timedelta

from equilibrage import FRAIS, gain_unitaire

DEFAUTS = {"distance": 6, "duree": 48.0, "gain_min": 4.5}


def evaluer_sources(paliers, courant, etat, maintenant, distance=6, duree=48.0, gain_min=4.5, frais=FRAIS):
    """Met à jour les chronomètres et l'éligibilité de chaque palier.

    paliers : {ID: (prix, bet)} ; courant : ID du palier courant ;
    etat : {ID: (eloigne_depuis, source_depuis)} (datetime ou None), état
    enregistré ; maintenant : datetime (UTC) ; duree en heures.

    Returns:
        (nouvel_etat, evenements, gains)
        nouvel_etat : {ID: (eloigne_depuis, source_depuis)} pour tous les paliers ;
        evenements : liste de dict (palier, evenement "eligible" / "fin", raison,
                     gain, distance, eloigne_depuis, source_depuis) ;
        gains : {ID: gain(S)} (0 sans palier au-dessus).
    """
    prix = {int(i): float(v[0]) for i, v in paliers.items() if v[0] is not None}
    nouvel, evenements, gains = {}, [], {}
    for i in sorted(prix):
        bet = float(paliers[i][1] or 0)
        g = gain_unitaire(prix, i, frais)
        gain = bet * g if g is not None else 0.0
        gains[i] = gain
        eloigne, source = etat.get(i, (None, None))
        d = abs(i - int(courant))
        if d < distance:
            eloigne = None
        elif eloigne is None:
            eloigne = maintenant
        eligible = (eloigne is not None and maintenant - eloigne >= timedelta(hours=duree) and gain > gain_min)
        if eligible and source is None:
            source = maintenant
            evenements.append({"palier": i, "evenement": "eligible", "raison": "source éligible",
                               "gain": gain, "distance": d, "eloigne_depuis": eloigne, "source_depuis": source})
        elif not eligible and source is not None:
            raison = ("retour du prix (distance < " + str(distance) + ")" if d < distance
                      else "gain ≤ " + f"{gain_min:g}".replace(".", ","))
            evenements.append({"palier": i, "evenement": "fin", "raison": raison, "gain": gain, "distance": d,
                               "eloigne_depuis": etat.get(i, (None, None))[0], "source_depuis": source})
            source = None
        nouvel[i] = (eloigne, source)
    return nouvel, evenements, gains


def reconstituer_chronos(executions, ids, distance=6):
    """Chronomètres reconstitués à partir de l'historique des ordres limites exécutés.

    executions : liste de (date, palier) des ordres limites exécutés, dans
    n'importe quel ordre ; ids : paliers de la grille.
    Rejoue l'historique : un palier est « éloigné » depuis la première
    exécution qui l'a mis à distance ≥ distance, sans retour depuis.

    Returns:
        {ID: datetime ou None} ; None aussi si aucun historique.
    """
    chronos = {int(i): None for i in ids}
    for date, palier in sorted(executions, key=lambda e: e[0]):
        for i in chronos:
            if abs(i - int(palier)) < distance:
                chronos[i] = None
            elif chronos[i] is None:
                chronos[i] = date
    return chronos
