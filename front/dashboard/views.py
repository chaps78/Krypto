"""Pages du front : ordres ouverts et journal du bot."""
from datetime import datetime, timezone

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


@login_required
def ordres_ouverts(request):
    """Ordres ouverts de toutes les stratégies actives, groupés par stratégie."""
    contexte = {"erreur": None, "strategies": []}
    try:
        contexte["bot"] = etat_bot()
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
    return render(request, "dashboard/ordres.html", contexte)


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
