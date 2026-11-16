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
import math
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


###########################################################################
#        CONSIGNE 2 : DÉCISION DE TRANSLATION (DÉPLACEMENT DU PIC)        #
###########################################################################
# Côtés du prix, après une vente au palier N (palier courant) :
#   palier i >= N : détient de l'actif (PEPE), vendu plus haut ;
#   palier i <  N : détient de la cotation (EUR), pour racheter plus bas.
# La cible T = N − 1 et son voisin T − 1 sont côté EUR, T + 1 = N côté PEPE.
# Source et receveur du même côté : écriture en base. Côtés opposés : ordre au
# marché (vente si la source détient du PEPE, achat si elle détient des EUR).
# Coût q × Δ : « payé » en euros si la source est côté EUR, « perte reconnue »
# si elle est côté PEPE (cet actif prévu à la vente plus haut est revendu plus bas).

DEFAUTS_DECISION = {"seuil": 15.0, "plancher": 3.0, "ordre_mini": 6.0}


def cote(i, courant):
    """'PEPE' si le palier i détient de l'actif (i >= palier courant), sinon 'EUR'."""
    return "PEPE" if int(i) >= int(courant) else "EUR"


def choisir_source(prix, bets, courant, cible, sources, distance=6, gain_min=4.5, frais=FRAIS):
    """Source de la translation : la plus lointaine des sources éligibles, à égalité celle du dessous.

    Une source est recontrôlée avec le palier courant de cette vente (distance
    et gain), et écartée si Δ = |p(S) − p(T)| ≥ p(T) (l'écart coûterait plus que
    la valeur déplacée).

    Returns:
        (ID de la source ou None, liste des sources écartées [(ID, motif)]).
    """
    pT = prix.get(cible)
    retenues, ecartees = [], []
    for S in sources:
        S = int(S)
        g, pS = gain_unitaire(prix, S, frais), prix.get(S)
        d = abs(S - int(courant))
        if g is None or pS is None or not pT:
            ecartees.append((S, "hors de la grille"))
        elif d < distance:
            ecartees.append((S, f"distance {d} < {distance}"))
        elif bets.get(S, 0.0) * g <= gain_min:
            ecartees.append((S, f"gain ≤ {gain_min:g}"))
        elif abs(pS - pT) >= pT:
            ecartees.append((S, "écart de prix ≥ prix du receveur"))
        else:
            retenues.append((d, S < int(courant), S))
    if not retenues:
        return None, ecartees
    return max(retenues)[2], ecartees


def decider_translation(paliers, courant, cible, benef, local, sources, prix_marche, seuil=15.0, plancher=3.0,
                        ordre_mini=6.0, distance=6, gain_min=4.5, frais=FRAIS, entier=True):
    """Décide la translation d'une vente (fonction pure).

    paliers : {ID: (prix, bet)} ; courant : palier de la vente (N) ; cible : T (N − 1) ;
    benef : B ; local : L (local du barème) ; sources : IDs des sources éligibles
    (consigne 1) ; prix_marche : prix actuel (valeur des ordres au marché).

    Le budget est utilisé en entier pour payer l'écart (q × Δ = budget), sauf si
    la source descendait sous le plancher ; le receveur peut dépasser le seuil.
    Cas A (gain(T) < seuil) : receveur T, budget L, q = min(L / Δ, bet(S) − plancher / g(S)),
    reste V = L − q × Δ (non nul seulement si le plancher limite) ajouté sur place à T.
    Cas B (gain(T) ≥ seuil) : budget B, aucune réinjection du barème ; receveurs
    T − 1 et T + 1 s'ils sont sous le seuil (moitié du budget chacun) ; q(N) × Δ(N)
    = part ; plancher de la source sur le total (réduction proportionnelle, le reste
    de B reste en gain) ; ordre au marché < ordre_mini : tout le budget au receveur
    du même côté que la source (s'il n'est pas servi : pas de translation).

    Returns:
        dict : applique, raison, cas, source, distance, position (côté de la source :
        "dessus" PEPE / "dessous" EUR), gain_source_avant / apres, recepteurs (liste
        de dict palier, q, delta, cout, ajout, gain_avant, gain_apres, ordre
        None / "SELL" / "BUY", valeur_ordre), q, cout, nature ("payé" / "perte
        reconnue"), vertical (V, cas A), budget, depense (euros réellement
        consommés : cas A L ou V, cas B coût payé ou 0), ecartees.
    """
    prix = {int(i): float(v[0]) for i, v in paliers.items() if v[0] is not None}
    bets = {int(i): float(v[1] or 0) for i, v in paliers.items()}
    T, N = int(cible), int(courant)
    benef, local = max(float(benef), 0.0), max(float(local), 0.0)
    res = {"applique": False, "cas": None, "source": None, "distance": None, "position": None,
           "gain_source_avant": None, "gain_source_apres": None, "recepteurs": [], "q": 0.0, "cout": 0.0,
           "nature": None, "vertical": None, "budget": None, "depense": None, "ecartees": []}
    gT, pT = gain_unitaire(prix, T, frais), prix.get(T)
    if gT is None or not pT or gT <= 0:
        return {**res, "raison": "cible hors de la grille ou sans gain"}
    betT = bets.get(T, 0.0)
    cas = "A" if betT * gT < seuil else "B"
    res["cas"] = cas
    S, ecartees = choisir_source(prix, bets, N, T, sources, distance, gain_min, frais)
    res["ecartees"] = ecartees
    if S is None:
        return {**res, "raison": "aucune source" + (f" ({len(ecartees)} écartée(s))" if ecartees else "")}
    gS, pS, betS = gain_unitaire(prix, S, frais), prix[S], bets.get(S, 0.0)
    cote_S = cote(S, N)
    nature = "perte reconnue" if cote_S == "PEPE" else "payé"
    q_source_max = betS - plancher / gS
    res.update({"source": S, "distance": abs(S - N), "position": "dessus" if cote_S == "PEPE" else "dessous",
                "gain_source_avant": betS * gS, "nature": nature, "prix_source": pS})

    def ordre(R):
        if cote(R, N) == cote_S:
            return None
        return "SELL" if cote_S == "PEPE" else "BUY"

    def arrondi(q):
        return float(math.floor(q)) if entier else q

    if cas == "A":
        delta = abs(pS - pT)
        limites = {"budget": local / delta if delta > 0 else math.inf, "plancher de la source": q_source_max}
        q = arrondi(max(min(limites.values()), 0.0))
        limite = min(limites, key=limites.get)
        res["budget"] = local
        if q <= 0:
            return {**res, "raison": f"q ≤ 0 (limite : {limite})"}
        o = ordre(T)
        if o and q * prix_marche < ordre_mini:
            return {**res, "raison": f"ordre au marché < {ordre_mini:g}"}
        cout = q * delta
        vertical = local - cout
        ajout = q + vertical / pT
        r = {"palier": T, "q": q, "delta": delta, "cout": cout, "ajout": ajout, "gain_avant": betT * gT,
             "gain_apres": (betT + ajout) * gT, "ordre": o, "valeur_ordre": q * prix_marche if o else None}
        return {**res, "applique": True, "raison": f"cas A, limité par : {limite}", "recepteurs": [r], "q": q,
                "cout": cout, "vertical": vertical, "gain_source_apres": (betS - q) * gS,
                "depense": local if nature == "payé" else vertical}

    # Cas B
    res["budget"] = benef
    candidats = []
    for R in (T - 1, T + 1):
        gR, pR = gain_unitaire(prix, R, frais), prix.get(R)
        if gR is None or not pR or gR <= 0 or bets.get(R, 0.0) * gR >= seuil:
            continue
        candidats.append(R)
    if not candidats:
        return {**res, "raison": "voisins à l'objectif"}

    def repartir(receveurs):
        """q par receveur (toute sa part du budget), puis plancher de la source sur le total."""
        part = benef / len(receveurs)
        qs = {}
        for R in receveurs:
            gR, pR = gain_unitaire(prix, R, frais), prix[R]
            delta = abs(pS - pR)
            qs[R] = max(part / delta if delta > 0 else 0.0, 0.0)
        total = sum(qs.values())
        if total > q_source_max:
            k = max(q_source_max, 0.0) / total if total > 0 else 0.0
            qs = {R: q * k for R, q in qs.items()}
        return {R: arrondi(q) for R, q in qs.items()}

    qs = repartir(candidats)
    trop_petits = [R for R in candidats if ordre(R) and qs[R] * prix_marche < ordre_mini]
    if trop_petits:
        meme_cote = [R for R in candidats if not ordre(R)]
        if not meme_cote:
            return {**res, "raison": f"ordre au marché < {ordre_mini:g} et voisin du même côté à l'objectif"}
        qs = repartir(meme_cote)
    recepteurs = []
    for R, q in qs.items():
        if q <= 0:
            continue
        gR, pR, betR = gain_unitaire(prix, R, frais), prix[R], bets.get(R, 0.0)
        delta = abs(pS - pR)
        o = ordre(R)
        recepteurs.append({"palier": R, "q": q, "delta": delta, "cout": q * delta, "ajout": q,
                           "gain_avant": betR * gR, "gain_apres": (betR + q) * gR, "ordre": o,
                           "valeur_ordre": q * prix_marche if o else None})
    if not recepteurs:
        return {**res, "raison": "q ≤ 0 (plancher de la source)"}
    q_total = sum(r["q"] for r in recepteurs)
    cout = sum(r["cout"] for r in recepteurs)
    return {**res, "applique": True, "raison": "cas B, " + " et ".join(str(r["palier"]) for r in recepteurs),
            "recepteurs": recepteurs, "q": q_total, "cout": cout, "gain_source_apres": (betS - q_total) * gS,
            "depense": cout if nature == "payé" else 0.0}
