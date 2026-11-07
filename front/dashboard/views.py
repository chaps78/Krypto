"""Pages du front : KPI (gain du mois et ordres ouverts), grille et journal du bot."""
import calendar
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import api_client

log = logging.getLogger(__name__)


def bloc(erreurs, titre, fonction, *args):
    """Exécute une partie de page ; en cas d'échec, note l'erreur et renvoie None.

    Ainsi un bloc en panne (API lente, réponse inattendue...) affiche un
    message mais n'empêche jamais le reste de la page de s'afficher.
    """
    try:
        return fonction(*args)
    except api_client.ApiError as e:
        erreurs.append(f"{titre} : {e}")
    except Exception as e:
        log.exception("Bloc %s en erreur", titre)
        erreurs.append(f"{titre} : erreur inattendue ({e.__class__.__name__})")
    return None


def parse_date(texte):
    """Convertit une date de la base du bot (ISO, UTC) en datetime, ou None."""
    try:
        return datetime.fromisoformat(texte)
    except (TypeError, ValueError):
        return None


def duree(depuis):
    """Durée lisible entre une date et maintenant (ex. "2 j 3 h", "45 min")."""
    if depuis is None:
        return ""
    s = int((datetime.now(timezone.utc) - depuis).total_seconds())
    j, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    if j:
        return f"{j} j {h} h"
    if h:
        return f"{h} h {m} min"
    return f"{m} min"


def nombre(x):
    """Affiche un nombre sans notation scientifique (utile pour PEPE : 0.00000419)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return x
    if x == int(x):
        return f"{int(x):,}".replace(",", " ")
    return f"{x:.10f}".rstrip("0")


def etat_bot():
    """Infos /health de l'API : date du dernier ordre et ancienneté."""
    sante = api_client.get("/health")
    dernier = parse_date(sante.get("dernier_ordre"))
    return {"dernier_ordre": dernier, "depuis": duree(dernier)}


def montant(x):
    """Montant arrondi à 2 décimales avec espace des milliers (ex. 1 234.57)."""
    return f"{x:,.2f}".replace(",", " ") if x is not None else "?"


def entier(texte, defaut, mini, maxi):
    """Entier lu dans l'URL, ramené entre mini et maxi ; defaut si illisible."""
    try:
        return min(max(int(texte), mini), maxi)
    except (TypeError, ValueError):
        return defaut


def decaler_mois(annee, mois, n):
    """Ajoute n mois (négatif pour reculer) à (annee, mois)."""
    i = annee * 12 + (mois - 1) + n
    return i // 12, i % 12 + 1


def gains_du_mois(request):
    """Gain du mois choisi par client, moyenne par jour et moyenne sur X mois.

    Paramètres d'URL : annee, mois (mois en cours par défaut, jamais dans le
    futur) et nb_mois (X, 3 par défaut). Le mois en cours compte les jours
    écoulés, aujourd'hui inclus ; un mois passé compte tous ses jours.
    """
    maintenant = datetime.now(timezone.utc)
    courant = (maintenant.year, maintenant.month)
    annee = entier(request.GET.get("annee"), courant[0], 2020, 2100)
    mois = entier(request.GET.get("mois"), courant[1], 1, 12)
    if (annee, mois) > courant:
        annee, mois = courant
    nb_mois = entier(request.GET.get("nb_mois"), 3, 1, 60)

    gains = api_client.get("/gains-mois", annee=annee, mois=mois, nb_mois=nb_mois)
    en_cours = (annee, mois) == courant
    jours = maintenant.day if en_cours else calendar.monthrange(annee, mois)[1]

    # Tous les clients ayant un gain sur la période, même nul le mois affiché
    du_mois = {c["id_client"]: c for c in gains["clients"]}
    cumul = {}
    for h in gains["historique"]:
        for c in h["clients"]:
            cu = cumul.setdefault(c["id_client"], {**c, "total": 0.0})
            cu["total"] += c["total"]
            cu["complet"] = cu["complet"] and c["complet"]
    clients = []
    for id_client in sorted(cumul):
        cu = cumul[id_client]
        c = du_mois.get(id_client, {**cu, "total": 0.0, "complet": True, "strategies": []})
        for s in c["strategies"]:
            s["gain_txt"] = montant(s["gain"])
            s["gain_base_txt"] = montant(s["gain_base"])
        c["total_txt"] = montant(c["total"])
        c["par_jour_txt"] = montant(c["total"] / jours)
        c["moyenne_txt"] = montant(cu["total"] / nb_mois)
        c["moyenne_complete"] = cu["complet"]
        clients.append(c)

    def lien(a, m):
        return f"?annee={a}&mois={m}&nb_mois={nb_mois}"

    precedent = decaler_mois(annee, mois, -1)
    suivant = decaler_mois(annee, mois, 1)
    debut = decaler_mois(annee, mois, -(nb_mois - 1))
    return {
        "annee": annee, "mois": mois, "nb_mois": nb_mois, "jours": jours,
        "en_cours": en_cours, "clients": clients,
        "debut_txt": f"{debut[1]:02d}/{debut[0]}",
        "lien_precedent": lien(*precedent),
        "lien_suivant": None if en_cours else lien(*suivant),
        "lien_courant": None if en_cours else lien(*courant),
    }


SEUIL_PETIT_SOLDE = 1.0  # EUR : en dessous, l'actif est regroupé dans « petits soldes »


def portefeuilles():
    """Portefeuilles Binance (route /wallets), mis en forme pour la page KPI.

    Une erreur ici n'empêche pas le reste de la page de s'afficher : elle est
    renvoyée dans "erreur" et montrée dans la carte Portefeuille uniquement.
    """
    try:
        w = api_client.get("/wallets")
    except api_client.ApiError as e:
        return {"erreur": str(e)}
    for c in w["comptes"]:
        for a in c["actifs"]:
            a["libre_txt"] = nombre(a["libre"])
            a["bloque_txt"] = nombre(a["bloque"]) if a["bloque"] else ""
            a["total_txt"] = nombre(a["total"])
            a["eur_txt"] = montant(a["eur"])
            a["usdt_txt"] = montant(a["usdt"])
        c["principaux"] = [a for a in c["actifs"] if a["eur"] is None or a["eur"] >= SEUIL_PETIT_SOLDE]
        c["petits"] = [a for a in c["actifs"] if a["eur"] is not None and a["eur"] < SEUIL_PETIT_SOLDE]
        c["petits_eur_txt"] = montant(sum(a["eur"] for a in c["petits"]))
        c["total_eur_txt"] = montant(c["total_eur"])
        c["total_usdt_txt"] = montant(c["total_usdt"])
    w["total_eur_txt"] = montant(w["total_eur"])
    w["total_usdt_txt"] = montant(w["total_usdt"])
    w["maj_dt"] = parse_date(w.get("maj"))
    return w


def ordres_ouverts():
    """Stratégies actives avec leurs ordres ouverts, mis en forme."""
    strategies = []
    for strat in api_client.get("/strategies", actif="true"):
        ordres = api_client.get(f"/strategies/{strat['symbol']}/open-orders")
        for o in ordres:
            debut = parse_date(o["date_debut"])
            o["ouvert_le"] = debut
            o["ouvert_depuis"] = duree(debut)
            o["limite_txt"] = nombre(o["limite"])
            o["montant_txt"] = nombre(o["montant"])
        strategies.append({**strat, "ordres": ordres})
    return strategies


@login_required
def kpi(request):
    """Page KPI : gain du mois, portefeuilles Binance, puis ordres ouverts.

    Chaque bloc est indépendant : une erreur dans l'un est affichée en haut
    de page sans empêcher les autres de s'afficher.
    """
    erreurs = []
    contexte = {
        "bot": bloc(erreurs, "Dernier ordre", etat_bot),
        "gains": bloc(erreurs, "Gain du mois", gains_du_mois, request),
        "wallets": bloc(erreurs, "Portefeuille", portefeuilles),
        "strategies": bloc(erreurs, "Ordres ouverts", ordres_ouverts) or [],
    }
    contexte["erreur"] = " · ".join(erreurs) or None
    return render(request, "dashboard/kpi.html", contexte)


FRAIS_BROKER = 0.00075  # 0,075 % de frais Binance, payés sur l'achat ET sur la vente


def gain_aller_retour(palier, dessus):
    """Gain net d'un achat au palier puis d'une vente au palier du dessus.

    Même quantité (bet du palier) : achat au prix du palier, vente au prix
    du palier du dessus, moins FRAIS_BROKER sur le montant de chacun des deux
    ordres. None pour le dernier palier (pas de palier au-dessus).
    """
    if dessus is None or palier["prix"] is None or dessus["prix"] is None or palier["bet"] is None:
        return None
    achat = palier["bet"] * palier["prix"]
    vente = palier["bet"] * dessus["prix"]
    return vente - achat - FRAIS_BROKER * (achat + vente)


def paliers_quantite(ordre):
    """Paliers dont le bet compose la quantité d'un ordre ouvert (cf. bininterface).

    L'ordre est enregistré sur le palier de son PRIX (id_ecart). Sa quantité
    vient d'autres paliers selon le sens et le niveau :
      - vente : paliers sous le prix, 1 (niveaux 1-2), 2 (niveau 3) ou 3 (niveau 4) ;
      - achat : palier du prix et au-dessus, 1, 2 ou 3 paliers de même.
    """
    n = int(ordre["niveau"] or 1)
    k = 1 if n <= 2 else (2 if n == 3 else 3)
    s = ordre["id_ecart"]
    return list(range(s - k, s)) if ordre["sens"] == "SELL" else list(range(s, s + k))


@login_required
def grille(request):
    """Tableau et graphique ecart_bet d'une stratégie : prix, quantité et valeur par palier.

    Seules les stratégies de settings.KRYPTO_GRILLE_SYMBOLS sont proposées
    (PEPEEUR_N91 par défaut, modifiable dans .env). Pour chaque ordre ouvert,
    la case prix de son palier est surlignée, ainsi que les paliers qui
    fournissent sa quantité (pour une vente : le palier du dessous).
    """
    autorises = settings.KRYPTO_GRILLE_SYMBOLS
    symbol = request.GET.get("symbol")
    if symbol not in autorises:
        symbol = autorises[0] if autorises else None
    contexte = {"erreur": None, "symbols": autorises, "symbol": symbol, "paliers": [], "strat": None}
    if symbol is None:
        contexte["erreur"] = "Aucune stratégie configurée (KRYPTO_GRILLE_SYMBOLS)."
        return render(request, "dashboard/grille.html", contexte)
    try:
        strat = contexte["strat"] = api_client.get(f"/strategies/{symbol}")
        ouverts = api_client.get(f"/strategies/{symbol}/open-orders")
        paliers = api_client.get(f"/strategies/{symbol}/grid")
        par_id = {p["id"]: p for p in paliers}
        for p in paliers:
            p["prix_txt"] = nombre(p["prix"])
            p["bet_txt"] = nombre(round(p["bet"]))
            p["valeur"] = p["prix"] * p["bet"]
            p["valeur_txt"] = montant(p["valeur"])
        cumul = 0.0
        for p in paliers:  # du palier le plus bas au plus haut (ordre de l'API)
            cumul += p["valeur"]
            p["cumul_txt"] = montant(cumul)
            p["gain"] = gain_aller_retour(p, par_id.get(p["id"] + 1))
            p["gain_txt"] = montant(p["gain"]) if p["gain"] is not None else ""
        for p in paliers:
            p["prix_de"] = p["quantite_de"] = p["ordre"] = None
            p["suite"] = False
        for o in ouverts:
            o["montant_txt"] = nombre(o["montant"])
            o["prix_txt"] = nombre(o["limite"])
            if o["id_ecart"] in par_id:
                par_id[o["id_ecart"]]["prix_de"] = o["sens"]
            ids = [i for i in paliers_quantite(o) if i in par_id]
            for i in ids:
                par_id[i]["quantite_de"] = o["sens"]
                par_id[i]["suite"] = True
            if ids:
                # Libellé complet sur le palier de quantité le plus proche du prix
                proche = par_id[min(ids, key=lambda i: abs(i - o["id_ecart"]))]
                proche["ordre"], proche["suite"] = o, False
        surlignes = [p for p in paliers if p["prix_de"] or p["quantite_de"]]
        if surlignes:
            surlignes[0]["ancre"] = True  # cible du lien « aller aux ordres ouverts »
        contexte["paliers"] = paliers
        contexte["nb_ouverts"] = len(ouverts)
        contexte["graphe"] = {
            "devise1": strat["devise1"], "devise2": strat["devise2"],
            "paliers": [{"id": p["id"], "prix": p["prix"] or 0, "bet": p["bet"] or 0, "gain": p["gain"],
                         "prix_de": p["prix_de"], "quantite_de": p["quantite_de"]}
                        for p in paliers],
            "ordres": [{"sens": o["sens"], "id_ecart": o["id_ecart"], "niveau": o["niveau"],
                        "prix": o["limite"], "montant": o["montant"]} for o in ouverts],
        }
    except api_client.ApiError as e:
        contexte["erreur"] = str(e)
    erreurs = []
    contexte["reinjection"] = bloc(erreurs, "Barème de réinjection", bareme_reinjection)
    contexte["erreur_reinjection"] = erreurs[0] if erreurs else None
    return render(request, "dashboard/grille.html", contexte)


def taux_pour(tranches, benef):
    """Taux d'un barème de l'API pour un bénéfice donné."""
    for t in tranches:
        if t["jusqua"] is None or benef < t["jusqua"]:
            return t["taux"]
    return None


def bareme_reinjection():
    """Barèmes local et UP fusionnés en tranches de gain : [{"de", "a", "local", "up"}]."""
    b = api_client.get("/reinjection")
    seuils = sorted({t["jusqua"] for t in b["local"] + b["up"] if t["jusqua"] is not None})
    bornes = [None] + seuils + [None]
    lignes = []
    for de, a in zip(bornes, bornes[1:]):
        point = de if de is not None else a - 1  # un gain représentatif de la tranche
        lignes.append({"de": de, "a": a, "local": taux_pour(b["local"], point), "up": taux_pour(b["up"], point)})
    return lignes


@login_required
def logs(request):
    """Journal du bot, filtrable par type, stratégie et nombre de lignes."""
    filtres = {
        "type": request.GET.get("type", "ERREUR"),
        "symbol": request.GET.get("symbol", ""),
        "limit": request.GET.get("limit", "100"),
    }
    if filtres["type"] not in ("ERREUR", "DEBUG"):
        filtres["type"] = "ERREUR"
    if filtres["limit"] not in ("50", "100", "500", "1000"):
        filtres["limit"] = "100"
    contexte = {"erreur": None, "lignes": [], "filtres": filtres, "symbols": []}
    try:
        contexte["symbols"] = [s["symbol"] for s in api_client.get("/strategies")]
        lignes = api_client.get("/logs", **filtres)
        for l in lignes:
            l["date_dt"] = parse_date(l["date"])
        contexte["lignes"] = lignes
    except api_client.ApiError as e:
        contexte["erreur"] = str(e)
    return render(request, "dashboard/logs.html", contexte)


@login_required
@require_POST
def piloter_bot(request, action):
    """Arrête ou démarre le bot (service krypto-bot) via l'API, puis revient à la page d'origine."""
    try:
        if action == "arreter":
            api_client.post("/bot/arreter")
            messages.success(request, "Arrêt demandé : le bot termine la stratégie en cours puis s'arrête (jusqu'à 2 min).")
        else:
            api_client.post("/bot/demarrer")
            messages.success(request, "Démarrage demandé : la pastille passe au vert au premier battement.")
    except api_client.ApiError as e:
        messages.error(request, str(e))
    suite = request.POST.get("suite", "")
    if not url_has_allowed_host_and_scheme(suite, allowed_hosts={request.get_host()}):
        suite = "/"
    return redirect(suite)
