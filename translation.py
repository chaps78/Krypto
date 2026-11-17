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
RESTE_MINI = 0.01   # budget restant (cotation) sous lequel on ne puise plus dans la source suivante (résidu d'arrondi)


def cote(i, courant):
    """'PEPE' si le palier i détient de l'actif (i >= palier courant), sinon 'EUR'."""
    return "PEPE" if int(i) >= int(courant) else "EUR"


def ordonner_sources(prix, bets, courant, cible, sources, distance=6, gain_min=4.5, frais=FRAIS):
    """Sources utilisables pour cette vente, dans l'ordre où on y puise.

    La plus lointaine d'abord, à égalité celle du dessous. Une source est
    recontrôlée avec le palier courant de cette vente (distance et gain), et
    écartée si Δ = |p(S) − p(T)| ≥ p(T) (l'écart coûterait plus que la valeur déplacée).

    Returns:
        (liste des IDs, liste des sources écartées [(ID, motif)]).
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
    return [r[2] for r in sorted(retenues, reverse=True)], ecartees


def choisir_source(prix, bets, courant, cible, sources, distance=6, gain_min=4.5, frais=FRAIS):
    """Première source de ordonner_sources() : (ID ou None, sources écartées)."""
    ordre, ecartees = ordonner_sources(prix, bets, courant, cible, sources, distance, gain_min, frais)
    return (ordre[0] if ordre else None), ecartees


def decider_translation(paliers, courant, cible, benef, local, sources, prix_marche, seuil=15.0, plancher=3.0,
                        ordre_mini=6.0, distance=6, gain_min=4.5, frais=FRAIS, entier=True):
    """Décide la translation d'une vente (fonction pure).

    paliers : {ID: (prix, bet)} ; courant : palier de la vente (N) ; cible : T (N − 1) ;
    benef : B ; local : L (local du barème) ; sources : IDs des sources éligibles
    (consigne 1) ; prix_marche : prix actuel (valeur des ordres au marché).

    Le budget paie l'écart (q × Δ) et il est utilisé en entier. On puise dans les
    sources l'une après l'autre (ordonner_sources) : quand une source atteint le
    plancher, le reste du budget est pris sur la suivante. Le receveur peut dépasser le seuil.
    Cas A (gain(T) < seuil) : receveur T, budget L ; ce qui reste quand toutes les
    sources sont au plancher (V) est ajouté sur place à T.
    Cas B (gain(T) ≥ seuil) : budget B, aucune réinjection du barème ; receveurs
    T − 1 et T + 1 s'ils sont sous le seuil (moitié du budget chacun). Une source qui
    ne couvre pas les deux parts est partagée au prorata ; le reste de B reste en gain.
    Ordres au marché : un seul, net (achats − ventes de toutes les paires source/receveur
    de côtés opposés). S'il vaut moins que ordre_mini : on ne garde que les paires du
    même côté (aucun ordre) ; en cas B, le budget est alors partagé entre les receveurs
    qu'une source du même côté peut servir. Sinon, pas de translation.

    Returns:
        dict : applique, raison, cas, source (première source utilisée), distance,
        position ("dessus" PEPE / "dessous" EUR), prix_source, gain_source_avant / apres
        (de cette première source), sources (détail par source : source, distance,
        position, prix, gain_avant, gain_apres, q, cout, nature), transferts (paires
        source, palier, q, delta, cout, ordre), recepteurs (par receveur : palier, q,
        delta, cout, ajout, gain_avant, gain_apres, ordre, valeur_ordre), q, cout,
        cout_paye, cout_reconnu, nature ("payé" / "perte reconnue" / "mixte"),
        ordre ("BUY" / "SELL" / None, ordre net), q_ordre, valeur_ordre, vertical
        (V, cas A), budget, depense (euros réellement consommés : coût payé + V), ecartees.
    """
    prix = {int(i): float(v[0]) for i, v in paliers.items() if v[0] is not None}
    bets = {int(i): float(v[1] or 0) for i, v in paliers.items()}
    T, N = int(cible), int(courant)
    benef, local = max(float(benef), 0.0), max(float(local), 0.0)
    res = {"applique": False, "cas": None, "source": None, "distance": None, "position": None,
           "prix_source": None, "gain_source_avant": None, "gain_source_apres": None, "sources": [],
           "transferts": [], "recepteurs": [], "q": 0.0, "cout": 0.0, "cout_paye": 0.0, "cout_reconnu": 0.0,
           "nature": None, "ordre": None, "q_ordre": 0.0, "valeur_ordre": None, "vertical": None,
           "budget": None, "depense": None, "ecartees": []}
    gT, pT = gain_unitaire(prix, T, frais), prix.get(T)
    if gT is None or not pT or gT <= 0:
        return {**res, "raison": "cible hors de la grille ou sans gain"}
    betT = bets.get(T, 0.0)
    cas = "A" if betT * gT < seuil else "B"
    res["cas"] = cas
    ordre_src, ecartees = ordonner_sources(prix, bets, N, T, sources, distance, gain_min, frais)
    res["ecartees"] = ecartees
    if not ordre_src:
        return {**res, "raison": "aucune source" + (f" ({len(ecartees)} écartée(s))" if ecartees else "")}
    S0 = ordre_src[0]
    res.update({"source": S0, "distance": abs(S0 - N), "position": "dessus" if cote(S0, N) == "PEPE" else "dessous",
                "prix_source": prix[S0], "gain_source_avant": bets.get(S0, 0.0) * gain_unitaire(prix, S0, frais)})

    def arrondi(q):
        return float(math.floor(q)) if entier else q

    def sens(S, R):
        """Ordre au marché nécessaire pour la paire (S, R), ou None (même côté)."""
        if cote(R, N) == cote(S, N):
            return None
        return "SELL" if cote(S, N) == "PEPE" else "BUY"

    def allouer(budgets, autorise):
        """Puise dans les sources, dans l'ordre, jusqu'à épuiser les budgets {R: montant}.

        Returns: liste des transferts {source, palier, q, delta, cout, ordre}.
        """
        reste = dict(budgets)
        dispo = {S: max(bets.get(S, 0.0) - plancher / gain_unitaire(prix, S, frais), 0.0) for S in ordre_src}
        transferts = []
        for S in ordre_src:
            Rs = [R for R in reste if reste[R] >= RESTE_MINI and autorise(S, R) and abs(prix[S] - prix[R]) > 0]
            if not Rs or dispo[S] <= 0:
                continue
            besoins = {R: reste[R] / abs(prix[S] - prix[R]) for R in Rs}
            k = min(1.0, dispo[S] / sum(besoins.values()))
            for R in Rs:
                q = arrondi(besoins[R] * k)
                if q <= 0:
                    continue
                delta = abs(prix[S] - prix[R])
                transferts.append({"source": S, "palier": R, "q": q, "delta": delta, "cout": q * delta,
                                   "ordre": sens(S, R)})
                reste[R] -= q * delta
                dispo[S] -= q
        return transferts

    def ordre_net(transferts):
        """(sens, quantité) de l'ordre au marché unique, achats − ventes."""
        net = sum(t["q"] if t["ordre"] == "BUY" else -t["q"] for t in transferts if t["ordre"])
        if abs(net) <= 0:
            return None, 0.0
        return ("BUY" if net > 0 else "SELL"), abs(net)

    def ordre_trop_petit(transferts):
        o, q = ordre_net(transferts)
        return o is not None and q * prix_marche < ordre_mini

    tous = lambda S, R: True
    meme_cote = lambda S, R: sens(S, R) is None

    if cas == "A":
        budgets = {T: local}
        res["budget"] = local
        if local <= 0:
            return {**res, "raison": "aucun budget (local nul)"}
        transferts = allouer(budgets, tous)
        if ordre_trop_petit(transferts):
            transferts = allouer(budgets, meme_cote)
            if not transferts:
                return {**res, "raison": f"ordre au marché < {ordre_mini:g}"}
    else:
        res["budget"] = benef
        candidats = []
        for R in (T - 1, T + 1):
            gR, pR = gain_unitaire(prix, R, frais), prix.get(R)
            if gR is None or not pR or gR <= 0 or bets.get(R, 0.0) * gR >= seuil:
                continue
            candidats.append(R)
        if not candidats:
            return {**res, "raison": "voisins à l'objectif"}
        if benef <= 0:
            return {**res, "raison": "aucun budget (bénéfice nul)"}
        transferts = allouer({R: benef / len(candidats) for R in candidats}, tous)
        if ordre_trop_petit(transferts):
            servis = [R for R in candidats if any(sens(S, R) is None for S in ordre_src)]
            if not servis:
                return {**res, "raison": f"ordre au marché < {ordre_mini:g} et voisin du même côté à l'objectif"}
            transferts = allouer({R: benef / len(servis) for R in servis}, meme_cote)
    if not transferts:
        return {**res, "raison": "q ≤ 0 (plancher des sources)"}

    cout = sum(t["cout"] for t in transferts)
    paye = sum(t["cout"] for t in transferts if cote(t["source"], N) == "EUR")
    vertical = local - cout if cas == "A" else None
    o, q_ordre = ordre_net(transferts)

    detail_sources = []
    for S in dict.fromkeys(t["source"] for t in transferts):
        gS, betS = gain_unitaire(prix, S, frais), bets.get(S, 0.0)
        qS = sum(t["q"] for t in transferts if t["source"] == S)
        detail_sources.append({"source": S, "distance": abs(S - N),
                               "position": "dessus" if cote(S, N) == "PEPE" else "dessous", "prix": prix[S],
                               "gain_avant": betS * gS, "gain_apres": (betS - qS) * gS, "q": qS,
                               "cout": sum(t["cout"] for t in transferts if t["source"] == S),
                               "nature": "perte reconnue" if cote(S, N) == "PEPE" else "payé"})
    recepteurs = []
    for R in dict.fromkeys(t["palier"] for t in transferts):
        gR, pR, betR = gain_unitaire(prix, R, frais), prix[R], bets.get(R, 0.0)
        tR = [t for t in transferts if t["palier"] == R]
        qR = sum(t["q"] for t in tR)
        ajout = qR + (vertical / pR if cas == "A" else 0.0)
        q_ord = sum(t["q"] for t in tR if t["ordre"])
        recepteurs.append({"palier": R, "q": qR, "delta": sum(t["cout"] for t in tR) / qR,
                           "cout": sum(t["cout"] for t in tR), "ajout": ajout, "gain_avant": betR * gR,
                           "gain_apres": (betR + ajout) * gR,
                           "ordre": next((t["ordre"] for t in tR if t["ordre"]), None), "q_ordre": q_ord,
                           "valeur_ordre": q_ord * prix_marche if q_ord else None})
    natures = {s["nature"] for s in detail_sources}
    premiere = detail_sources[0]
    utilisees = ", ".join(str(s["source"]) for s in detail_sources)
    raison = (f"cas A, source(s) {utilisees}" + (" ; reste V sur place" if vertical and vertical >= 0.01 else "")
              if cas == "A" else f"cas B, {' et '.join(str(r['palier']) for r in recepteurs)} ; source(s) {utilisees}")
    return {**res, "applique": True, "raison": raison, "source": premiere["source"],
            "distance": premiere["distance"], "position": premiere["position"], "prix_source": premiere["prix"],
            "gain_source_avant": premiere["gain_avant"], "gain_source_apres": premiere["gain_apres"],
            "sources": detail_sources, "transferts": transferts, "recepteurs": recepteurs,
            "q": sum(t["q"] for t in transferts), "cout": cout, "cout_paye": paye, "cout_reconnu": cout - paye,
            "nature": natures.pop() if len(natures) == 1 else "mixte",
            "ordre": o, "q_ordre": q_ordre, "valeur_ordre": q_ordre * prix_marche if o else None,
            "vertical": vertical, "depense": paye + (vertical or 0.0)}
