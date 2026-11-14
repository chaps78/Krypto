"""Équilibrage du mode oscillation (étape 3) : règle de décision, fonction pure.

Après une vente, la cible T (palier qui reçoit le local, racheté par le
nouvel achat) peut emprunter q unités d'actif au bet d'un voisin plus fort P
(T−3..T+3), sans jamais inverser les rôles. Aucun accès à Binance ni à la base
ici : tout est passé en paramètre, ce qui permet de tester chaque cas.

Définitions (consigne étape 3) :
    g(i)    = p(i+1) − p(i) − f × (p(i) + p(i+1))      gain unitaire du palier i
    gain(i) = bet(i) × g(i)
    L       = local du barème (taux_local × B), budget = min(B, L)
    Δ       = |p(P) − p(T)|, coût du transfert = q × Δ (payé sur le budget)
    V       = L − q × Δ : reste du local, ajouté sur place à T (V / p(T))
    q max   = min( budget / Δ,
                   écart : [bet(P)g(P) − k g(T)(bet(T) + L/p(T))] / [g(P) + k g(T)(1 − Δ/p(T))],  k = 1 + écart %
                   plancher (si gain(P) >= seuil) : bet(P) − seuil / g(P),
                   bet(P) )
Marges (éviter les transferts minuscules, donc les ventes sous l'ordre minimal) :
    déclenchement : P n'est éligible que si gain(P) >= (1 + déclenchement %) ×
                    gain de la cible après réinjection normale ; il prête ensuite
                    jusqu'à la limite d'écart (1 + écart %) ;
    marge plancher : un prêteur à l'objectif (gain(P) >= seuil) n'est éligible
                    que si gain(P) >= seuil + marge ; il ne descend pas sous le seuil.
Ordre des décisions à chaque vente : translation (étape ultérieure), puis
équilibrage, sinon réinjection normale. decider_equilibrage() ne traite que
l'équilibrage ; l'appelant peut tester une translation avant.
"""
import math

FRAIS = 0.00075   # 0,075 % par ordre, même taux que calcul_benefice (sqlInterface)
DEFAUTS = {"distance": 3, "ecart": 20.0, "seuil": 15.0, "ordre_mini": 6.0, "declenchement": 30.0, "marge_plancher": 1.0}


def gain_unitaire(prix, i, frais=FRAIS):
    """g(i), ou None si le palier i ou i+1 n'existe pas."""
    p, dessus = prix.get(i), prix.get(i + 1)
    if p is None or dessus is None:
        return None
    return dessus - p - frais * (p + dessus)


def decider_equilibrage(paliers, cible, benef, local, prix_marche, distance=3, ecart=20.0, seuil=15.0,
                        ordre_mini=6.0, declenchement=30.0, marge_plancher=1.0, frais=FRAIS, entier=True):
    """Décide l'équilibrage d'une vente.

    paliers : {ID: (prix, bet)} ; cible : T ; benef : B ; local : L (cotation) ;
    prix_marche : prix actuel (pour le minimum de la vente d'un prêteur au-dessus).

    Returns:
        dict : applique (bool), raison, cible, gain_cible_avant, gain_cible_apres,
        preteur, position ("dessous" / "dessus"), gain_preteur_avant,
        gain_preteur_apres, q, cout (q × Δ), vertical (V), ajout_cible
        (q + V / p(T), à ajouter au bet de T), candidats (détail par prêteur).
        Sans équilibrage, ajout_cible = L / p(T) (réinjection normale) et
        gain_cible_apres est celui de la réinjection normale (toujours donné
        dans gain_cible_normal).
    """
    prix = {int(i): float(v[0]) for i, v in paliers.items() if v[0] is not None}
    bets = {int(i): float(v[1] or 0) for i, v in paliers.items()}
    T = int(cible)
    benef, local = max(float(benef), 0.0), max(float(local), 0.0)
    res = {"applique": False, "cible": T, "preteur": None, "position": None, "q": 0.0, "cout": 0.0,
           "vertical": local, "gain_preteur_avant": None, "gain_preteur_apres": None, "candidats": []}
    gT, pT = gain_unitaire(prix, T, frais), prix.get(T)
    if gT is None or not pT:
        return {**res, "raison": "cible hors de la grille", "ajout_cible": 0.0,
                "gain_cible_avant": None, "gain_cible_apres": None}
    betT = bets.get(T, 0.0)
    res.update({"gain_cible_avant": betT * gT, "ajout_cible": local / pT,
                "gain_cible_apres": (betT + local / pT) * gT, "gain_cible_normal": (betT + local / pT) * gT})
    if gT <= 0:
        return {**res, "raison": "gain unitaire de la cible nul ou négatif"}
    if betT * gT >= seuil:
        return {**res, "raison": f"cible à {seuil:g} € ou plus"}
    budget = min(benef, local)
    if budget <= 0:
        return {**res, "raison": "aucun budget de translation (B ou local nul)"}

    k = 1 + ecart / 100
    for P in [T - d for d in range(distance, 0, -1)] + [T + d for d in range(1, distance + 1)]:
        gP, pP, betP = gain_unitaire(prix, P, frais), prix.get(P), bets.get(P, 0.0)
        if gP is None or pP is None or betP <= 0 or gP <= 0:
            continue
        delta = abs(pP - pT)
        c = {"preteur": P, "position": "dessus" if P > T else "dessous", "gain_avant": betP * gP,
             "delta": delta, "g": gP, "bet": betP, "q": 0.0}
        if betP * gP < (1 + declenchement / 100) * res["gain_cible_normal"]:
            c["eligible"], c["limite"], c["motif"] = False, "déclenchement", f"gain < {1 + declenchement / 100:g} × cible"
            res["candidats"].append(c)
            continue
        if seuil <= betP * gP < seuil + marge_plancher:
            c["eligible"], c["limite"], c["motif"] = False, "plancher", f"à l'objectif, gain < {seuil + marge_plancher:g}"
            res["candidats"].append(c)
            continue
        limites = {
            "budget": budget / delta if delta > 0 else math.inf,
            "ecart": (betP * gP - k * gT * (betT + local / pT)) / (gP + k * gT * (1 - delta / pT)),
            "plancher": betP - seuil / gP if betP * gP >= seuil else math.inf,
            "bet": betP,
        }
        q = min(limites.values())
        c["limite"] = min(limites, key=limites.get)
        if entier and q > 0:
            q = float(math.floor(q))
        c["q"] = max(q, 0.0)
        if q <= 0:
            c["eligible"], c["motif"] = False, f"q max nul ({c['limite']})"
        elif P > T and q * prix_marche < ordre_mini:
            c["eligible"], c["motif"] = False, f"ordre < {ordre_mini:g} €"
        else:
            c["eligible"], c["motif"] = True, f"limité par {c['limite']}"
        res["candidats"].append(c)

    eligibles = [c for c in res["candidats"] if c["eligible"]]
    if not eligibles:
        petits = [c for c in res["candidats"] if c.get("motif", "").startswith("ordre <")]
        raison = "aucun prêteur éligible" + (f" (ordre < {ordre_mini:g} € pour "
                                              + ", ".join(str(c["preteur"]) for c in petits) + ")" if petits else "")
        return {**res, "raison": raison}
    # Plus fort gain, puis le plus proche, puis celui du dessous
    choix = max(eligibles, key=lambda c: (c["gain_avant"], -abs(c["preteur"] - T), c["position"] == "dessous"))
    q, delta = choix["q"], choix["delta"]
    cout = q * delta
    vertical = local - cout
    ajout = q + vertical / pT
    return {**res, "applique": True, "raison": f"prêteur {choix['preteur']} ({choix['position']}), {choix['motif']}",
            "preteur": choix["preteur"], "position": choix["position"],
            "gain_preteur_avant": choix["gain_avant"], "gain_preteur_apres": (choix["bet"] - q) * choix["g"],
            "q": q, "cout": cout, "vertical": vertical, "ajout_cible": ajout,
            "gain_cible_apres": (betT + ajout) * gT}
