"""Réserves hors grille et choix de la source de la réinjection (fonctions pures).

Partagé par le bot (trader.py) et l'API (api.py). Aucun accès à Binance ni à
la base ici : tout est passé en paramètre, ce qui permet de tester chaque cas.

Vocabulaire : une stratégie trade un *actif* (devise1, ex. PEPE) contre une
devise de *cotation* (devise2, ex. EUR).
"""
from datetime import datetime, timedelta, timezone

VALEUR_MINI = 6.0            # en cotation : en dessous, Binance refuserait l'ordre au marché
AGE_MAX_MOYENNES = timedelta(hours=2)
MODES = ("EUR", "observation", "auto")
CHOIX_INSUFFISANT = ("suspendre", "eur_negatif")


def besoins_grille(paliers, palier):
    """Ce que la grille engage de chaque côté du palier courant.

    paliers : itérable de (ID, prix, bet). palier : ID du dernier ordre LIMIT
    exécuté. Les paliers >= palier sont détenus en actif (vendus en montant :
    bet[p] au prix p+1), ceux en dessous en cotation (achetés en descendant).

    Returns:
        (cotation nécessaire = Σ bet × prix sous le palier,
         actif nécessaire    = Σ bet à partir du palier)
    """
    cotation = actif = 0.0
    for i, prix, bet in paliers:
        bet, prix = float(bet or 0), float(prix or 0)
        if int(i) < int(palier):
            cotation += bet * prix
        else:
            actif += bet
    return cotation, actif


def calculer(wallet_cotation, wallet_actif, paliers, palier, prix):
    """Réserves = soldes (libres + bloqués) − besoins de la grille."""
    grille_cotation, grille_actif = besoins_grille(paliers, palier)
    reserve_actif = wallet_actif - grille_actif
    return {
        "palier": int(palier), "prix": prix,
        "wallet_cotation": wallet_cotation, "grille_cotation": grille_cotation,
        "reserve_cotation": wallet_cotation - grille_cotation,
        "wallet_actif": wallet_actif, "grille_actif": grille_actif,
        "reserve_actif": reserve_actif,
        "reserve_actif_valeur": reserve_actif * prix if prix else None,
    }


def moyennes_valides(ma, maintenant=None):
    """Vrai si ma = {"ouverture": iso, "ma7", "ma25"} vient d'une bougie close il y a 2 h au plus."""
    if not ma or ma.get("ma7") is None or ma.get("ma25") is None:
        return False
    maintenant = maintenant or datetime.now(timezone.utc)
    try:
        cloture = datetime.fromisoformat(ma["ouverture"]) + timedelta(hours=1)
    except (TypeError, ValueError):
        return False
    return maintenant - cloture <= AGE_MAX_MOYENNES


def decider_source(benef, local, up, down, ma, ecart_min_ma, reserves, up_tmp,
                   si_insuffisant="suspendre", entier=True, maintenant=None):
    """Choisit comment financer la part capital du local et du down (consigne 2).

    - Le bénéfice B finance d'abord le local, puis le down ; le reste
      (local − B, down − reste de B) est la part capital.
    - Source préférée : PEPE (actif) si MA7 > MA25 × (1 + ecart_min_ma %),
      avec des moyennes de 2 h au plus ; sinon EUR (cotation).
    - Le up est toujours financé en cotation (cumul up_TMP, comme aujourd'hui).
    - Une vente de financement de moins de VALEUR_MINI est remplacée par la cotation.
    - Faisabilité, après réinjection (up_tmp déjà en attente compris) :
        source cotation : reserve_cotation − up_tmp − (local + down + up) >= 0
        source actif    : reserve_actif − quantité vendue >= 0, et la réserve de
                          cotation (qui paie toujours le up) + valeur vendue >= 0
      Source préférée impossible -> l'autre ; les deux impossibles -> suspension,
      sauf si si_insuffisant == "eur_negatif" (cotation quand même).
    - Réserves inconnues (wallet illisible) -> cotation, sans contrôle (comportement d'avant).

    Returns:
        dict : source ("EUR" | "PEPE" | "SUSPENDU"), raison, preferee,
        capital (part capital totale local + down + up, en cotation),
        a_vendre (quantité d'actif à vendre, 0 si cotation), valeur_vente,
        reserve_cotation_apres, reserve_actif_apres.
    """
    benef = max(float(benef), 0.0)
    cap_local = max(local - benef, 0.0)
    reste = max(benef - local, 0.0)
    cap_down = max(down - reste, 0.0)
    reste = max(reste - down, 0.0)
    capital = cap_local + cap_down + max(up - reste, 0.0)
    a_financer = cap_local + cap_down

    if moyennes_valides(ma, maintenant):
        seuil = ma["ma25"] * (1 + (ecart_min_ma or 0) / 100)
        preferee = "PEPE" if ma["ma7"] > seuil else "EUR"
        raison = f"MA7 {'>' if preferee == 'PEPE' else '≤'} MA25" + (
            f" + {ecart_min_ma:g} %" if ecart_min_ma else "")
    else:
        preferee, raison = "EUR", "moyennes indisponibles ou de plus de 2 h"

    res = {"preferee": preferee, "capital": capital, "a_vendre": 0.0, "valeur_vente": 0.0,
           "reserve_cotation_apres": None, "reserve_actif_apres": None}
    if not reserves or reserves.get("reserve_cotation") is None or not reserves.get("prix"):
        return {**res, "source": "EUR", "raison": raison + " ; réserves inconnues : EUR sans contrôle"}

    prix = reserves["prix"]
    qte = a_financer / prix
    if entier:
        qte = float(int(qte))
    valeur = qte * prix
    base = reserves["reserve_cotation"] - (up_tmp or 0) - (local + down + up)
    scenarios = {
        "EUR": {"reserve_cotation_apres": base, "reserve_actif_apres": reserves["reserve_actif"],
                "a_vendre": 0.0, "valeur_vente": 0.0},
        "PEPE": {"reserve_cotation_apres": base + valeur, "reserve_actif_apres": reserves["reserve_actif"] - qte,
                 "a_vendre": qte, "valeur_vente": valeur},
    }

    def possible(s):
        """Cotation : sa réserve doit rester >= 0. Actif : réserve d'actif ET de cotation (le up) >= 0."""
        sc = scenarios[s]
        if s == "EUR":
            return sc["reserve_cotation_apres"] >= 0
        return valeur >= VALEUR_MINI and sc["reserve_actif_apres"] >= 0 and sc["reserve_cotation_apres"] >= 0

    if a_financer <= 0:
        preferee_effective, raison = "EUR", raison + " ; aucune part capital à financer (B couvre local et down)"
    elif preferee == "PEPE" and valeur < VALEUR_MINI:
        preferee_effective, raison = "EUR", raison + f" ; vente de {valeur:.2f} < {VALEUR_MINI:g} : EUR"
    else:
        preferee_effective = preferee
    autre = "EUR" if preferee_effective == "PEPE" else "PEPE"
    if possible(preferee_effective):
        return {**res, **scenarios[preferee_effective], "source": preferee_effective, "raison": raison}
    if possible(autre):
        return {**res, **scenarios[autre], "source": autre,
                "raison": raison + f" ; réserve {preferee_effective} insuffisante : bascule {autre}"}
    if si_insuffisant == "eur_negatif":
        return {**res, **scenarios["EUR"], "source": "EUR",
                "raison": raison + " ; réserves insuffisantes : EUR en négatif (choix du propriétaire)"}
    return {**res, **scenarios["EUR"], "a_vendre": 0.0, "valeur_vente": 0.0, "source": "SUSPENDU",
            "raison": raison + " ; réserves insuffisantes : réinjection suspendue"}
