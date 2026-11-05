"""Pages du front : KPI (gain du mois et ordres ouverts), grille et journal du bot."""
import calendar
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import api_client


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


@login_required
def kpi(request):
    """Page KPI : gain du mois par client, puis ordres ouverts des stratégies actives."""
    contexte = {"erreur": None, "strategies": [], "gains": None}
    try:
        contexte["bot"] = etat_bot()
        contexte["gains"] = gains_du_mois(request)
        for strat in api_client.get("/strategies", actif="true"):
            ordres = api_client.get(f"/strategies/{strat['symbol']}/open-orders")
            for o in ordres:
                debut = parse_date(o["date_debut"])
                o["ouvert_le"] = debut
                o["ouvert_depuis"] = duree(debut)
                o["limite_txt"] = nombre(o["limite"])
                o["montant_txt"] = nombre(o["montant"])
            contexte["strategies"].append({**strat, "ordres": ordres})
    except api_client.ApiError as e:
        contexte["erreur"] = str(e)
    return render(request, "dashboard/kpi.html", contexte)


@login_required
def grille(request):
    """Tableau ecart_bet d'une stratégie : prix, quantité, UP et ajout par palier.

    Seules les stratégies de settings.KRYPTO_GRILLE_SYMBOLS sont proposées
    (PEPEEUR_N91 par défaut, modifiable dans .env). Les paliers portant un
    ordre ouvert sont mis en évidence.
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
        contexte["strat"] = api_client.get(f"/strategies/{symbol}")
        ouverts = {o["id_ecart"]: o for o in api_client.get(f"/strategies/{symbol}/open-orders")}
        paliers = api_client.get(f"/strategies/{symbol}/grid")
        for p in paliers:
            p["prix_txt"] = nombre(p["prix"])
            p["bet_txt"] = nombre(round(p["bet"]))
            p["valeur_txt"] = montant(p["prix"] * p["bet"])
            p["ajout_txt"] = nombre(round(p["ajout"])) if p["ajout"] is not None else ""
            p["ordre"] = ouverts.get(p["id"])
            if p["ordre"]:
                p["ordre"]["montant_txt"] = nombre(p["ordre"]["montant"])
        premier = next((p for p in paliers if p["ordre"]), None)
        if premier:
            premier["ancre"] = True  # cible du lien « aller aux ordres ouverts »
        contexte["paliers"] = paliers
        contexte["nb_ouverts"] = len(ouverts)
    except api_client.ApiError as e:
        contexte["erreur"] = str(e)
    return render(request, "dashboard/grille.html", contexte)


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
