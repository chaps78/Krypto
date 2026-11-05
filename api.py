"""API HTTP en lecture seule sur DB.db, destinée au front (accès via tunnel SSH).

Lancement sur le serveur du bot :
    uvicorn api:app --host 127.0.0.1 --port 8000

L'API n'écoute que sur 127.0.0.1 : elle n'est joignable que depuis le serveur
lui-même, donc via un tunnel SSH. La base est ouverte en mode lecture seule
(mode=ro) : l'API ne peut pas la modifier. Les clés API et secrets des clients
ne sont jamais renvoyés.

Variables d'environnement (optionnelles) :
    KRYPTO_DB         chemin de la base (défaut : DB.db à côté de ce fichier)
    KRYPTO_API_TOKEN  si défini, chaque requête doit envoyer l'en-tête
                      "Authorization: Bearer <token>"
    KRYPTO_HEARTBEAT  fichier de battement du bot (défaut : bot.heartbeat à côté)
    KRYPTO_BOT_DELAI  secondes sans battement avant de considérer le bot
                      arrêté ou figé (défaut : 180)

Documentation interactive : http://127.0.0.1:8000/docs
"""
import json
import os
import sqlite3
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("KRYPTO_DB", os.path.join(BASE_DIR, "DB.db"))
API_TOKEN = os.environ.get("KRYPTO_API_TOKEN")
HEARTBEAT = os.environ.get("KRYPTO_HEARTBEAT", os.path.join(BASE_DIR, "bot.heartbeat"))
BOT_DELAI = int(os.environ.get("KRYPTO_BOT_DELAI", "180"))


def check_token(authorization: str | None = Header(default=None)):
    """Vérifie l'en-tête Authorization si KRYPTO_API_TOKEN est défini."""
    if API_TOKEN and authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Token invalide")


app = FastAPI(title="Krypto API", version="1.0", dependencies=[Depends(check_token)])


def query(sql, params=()):
    """Exécute une requête en lecture seule et renvoie une liste de dict.

    Une connexion par appel : simple et sans problème de partage entre threads.
    timeout=10 laisse le temps au bot de terminer une écriture en cours.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="Base introuvable")
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def strategy_or_404(symbol):
    """Renvoie la ligne Devises d'une stratégie, ou une erreur 404."""
    rows = query(STRATEGY_SQL + " WHERE symbol = ?", (symbol,))
    if not rows:
        raise HTTPException(status_code=404, detail=f"Stratégie {symbol} inconnue")
    return rows[0]


STRATEGY_SQL = """
    SELECT symbol, DEVISE1 AS devise1, DEVISE2 AS devise2, client AS id_client,
           actif, down, local, up, epargne_percent, factu_percent,
           dev_entiere, Obj_gain AS obj_gain,
           benef_all, benef_TMP AS benef_tmp, epargne, factu, up_TMP AS up_tmp
    FROM Devises
"""


@app.get("/health")
def health():
    """Etat de l'API et date du dernier ordre enregistré par le bot."""
    last = query("SELECT MAX(date_debut) AS dernier_ordre FROM Ordres")[0]
    return {"status": "ok", **last}


@app.get("/bot")
def bot():
    """Etat du bot de trading.

    en_marche est vrai si trader.py a écrit son battement il y a moins de
    KRYPTO_BOT_DELAI secondes. service donne l'état systemd de krypto-bot
    ("active", "inactive", "failed"... ou null si inconnu) : un service
    "active" sans battement récent signifie que le bot est figé.
    """
    try:
        dernier = datetime.fromtimestamp(os.path.getmtime(HEARTBEAT), timezone.utc)
        age = int((datetime.now(timezone.utc) - dernier).total_seconds())
    except OSError:
        dernier, age = None, None
    try:
        service = subprocess.run(["systemctl", "is-active", "krypto-bot"],
                                 capture_output=True, text=True, timeout=3).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        service = None
    return {
        "en_marche": age is not None and age < BOT_DELAI,
        "dernier_battement": dernier.isoformat() if dernier else None,
        "age_secondes": age,
        "service": service,
    }


@app.get("/clients")
def clients():
    """Liste des comptes (sans clés API, secrets ni chat Telegram)."""
    return query("SELECT ID_client AS id_client, nom, devise_base FROM client ORDER BY ID_client")


@app.get("/strategies")
def strategies(actif: bool | None = None, id_client: int | None = None):
    """Liste des stratégies, filtrable par état actif et par client."""
    where, params = [], []
    if actif is not None:
        where.append("actif = ?")
        params.append(1 if actif else 0)
    if id_client is not None:
        where.append("client = ?")
        params.append(id_client)
    sql = STRATEGY_SQL + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY symbol"
    return query(sql, params)


@app.get("/strategies/{symbol}")
def strategy(symbol: str):
    """Paramètres et compteurs d'une stratégie."""
    return strategy_or_404(symbol)


@app.get("/strategies/{symbol}/grid")
def grid(symbol: str):
    """Grille de la stratégie : paliers (prix, bet, UP) et ajouts cumulés."""
    strategy_or_404(symbol)
    return query(
        """SELECT e.ID AS id, e.prix, e.bet, e.UP AS up, a.ajout
           FROM ecart_bet e
           LEFT JOIN ajout a ON a.symbol = e.symbol AND a.ID_ecart = e.ID
           WHERE e.symbol = ? ORDER BY e.ID""",
        (symbol,),
    )


ORDER_SQL = """
    SELECT ID AS id, symbol, sens, type, status, montant, limite, montant_execute,
           ID_ecart AS id_ecart, niveau, flag_ajout, benefice, ID_client AS id_client,
           date_debut, date_fin
    FROM Ordres
"""


@app.get("/strategies/{symbol}/orders")
def orders(
    symbol: str,
    status: str | None = Query(default=None, description="ex. FILLED, NEW, CANCELED"),
    depuis: str | None = Query(default=None, description="date de début AAAA-MM-JJ"),
    limit: int = Query(default=100, ge=1, le=5000),
):
    """Historique des ordres d'une stratégie, du plus récent au plus ancien."""
    where, params = ["symbol = ?"], [symbol]
    if status:
        where.append("status = ?")
        params.append(status)
    if depuis:
        where.append("date_debut >= ?")
        params.append(depuis)
    params.append(limit)
    return query(ORDER_SQL + " WHERE " + " AND ".join(where) + " ORDER BY date_debut DESC LIMIT ?", params)


@app.get("/strategies/{symbol}/open-orders")
def open_orders(symbol: str):
    """Ordres actuellement ouverts (NEW ou partiellement exécutés) selon la base."""
    return query(
        ORDER_SQL + " WHERE symbol = ? AND status IN ('NEW', 'PARTIALLY_FILLED') ORDER BY sens",
        (symbol,),
    )


@app.get("/strategies/{symbol}/gains")
def gains(
    symbol: str,
    periode: str = Query(default="jour", pattern="^(jour|mois)$"),
    jours: int = Query(default=30, ge=1, le=3650, description="historique en jours"),
):
    """Bénéfice cumulé et nombre d'ordres exécutés, par jour ou par mois (date de fin)."""
    longueur = 10 if periode == "jour" else 7
    depuis = (datetime.now(timezone.utc) - timedelta(days=jours)).strftime("%Y-%m-%d")
    return query(
        f"""SELECT substr(date_fin, 1, {longueur}) AS periode,
                   ROUND(SUM(benefice), 8) AS benefice, COUNT(*) AS nb_ordres
            FROM Ordres
            WHERE symbol = ? AND status = 'FILLED' AND date_fin >= ?
            GROUP BY periode ORDER BY periode""",
        (symbol, depuis),
    )


def prix_binance(paire):
    """Prix public Binance d'une paire (ex. BTCEUR), sans clé API, ou None."""
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={paire}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return float(json.load(resp)["price"])
    except (OSError, ValueError, KeyError):
        return None


def taux_conversion(devise, base, cache):
    """Taux pour convertir devise -> base : paire directe, sinon paire inverse."""
    if devise == base:
        return 1.0
    if (devise, base) not in cache:
        taux = prix_binance(devise + base)
        if taux is None:
            inverse = prix_binance(base + devise)
            taux = 1 / inverse if inverse else None
        cache[(devise, base)] = taux
    return cache[(devise, base)]


def decaler_mois(annee, mois, n):
    """Ajoute n mois (négatif pour reculer) à (annee, mois)."""
    i = annee * 12 + (mois - 1) + n
    return i // 12, i % 12 + 1


@app.get("/gains-mois")
def gains_mois(
    annee: int | None = Query(default=None, ge=2020, le=2100),
    mois: int | None = Query(default=None, ge=1, le=12),
    nb_mois: int = Query(default=1, ge=1, le=60, description="mois d'historique, mois affiché inclus"),
):
    """Gain d'un mois par client, comme KPI.py gain_month_global.

    Même règle que KPI.py : somme de Ordres.benefice des ordres dont date_debut
    est dans le mois, pour toutes les stratégies du client (actives ou non).
    Chaque gain est converti dans la devise de base du client au prix Binance
    actuel (prix public, sans clé). Mois en cours par défaut.
    Si un taux est introuvable, convertible=false et le total l'ignore.

    clients : détail du mois demandé, par client et par stratégie.
    historique : total par client pour chacun des nb_mois mois finissant au
    mois demandé (du plus ancien au plus récent), pour calculer une moyenne.
    """
    maintenant = datetime.now(timezone.utc)
    annee = annee or maintenant.year
    mois = mois or maintenant.month
    debut = decaler_mois(annee, mois, -(nb_mois - 1))
    fin = decaler_mois(annee, mois, 1)
    lignes = query(
        """SELECT substr(o.date_debut, 1, 7) AS periode, o.symbol,
                  d.DEVISE2 AS devise, d.client AS id_client,
                  c.nom, c.devise_base AS base, SUM(o.benefice) AS gain
           FROM Ordres o
           JOIN Devises d ON d.symbol = o.symbol
           JOIN client c ON c.ID_client = d.client
           WHERE o.date_debut >= ? AND o.date_debut < ?
           GROUP BY periode, o.symbol HAVING gain IS NOT NULL
           ORDER BY d.client, o.symbol""",
        (f"{debut[0]}-{debut[1]:02d}", f"{fin[0]}-{fin[1]:02d}"),
    )
    periodes = [decaler_mois(debut[0], debut[1], i) for i in range(nb_mois)]
    par_mois = {f"{a}-{m:02d}": {} for a, m in periodes}
    cache = {}
    for l in lignes:
        clients = par_mois.get(l["periode"])
        if clients is None:
            continue
        c = clients.setdefault(l["id_client"], {
            "id_client": l["id_client"], "nom": l["nom"], "base": l["base"],
            "total": 0.0, "complet": True, "strategies": []})
        taux = taux_conversion(l["devise"], l["base"], cache)
        converti = l["gain"] * taux if taux is not None else None
        if converti is None:
            c["complet"] = False
        else:
            c["total"] += converti
        c["strategies"].append({"symbol": l["symbol"], "gain": l["gain"], "devise": l["devise"],
                                "gain_base": converti, "convertible": converti is not None})
    historique = [
        {"annee": a, "mois": m, "clients": [
            {k: c[k] for k in ("id_client", "nom", "base", "total", "complet")}
            for c in par_mois[f"{a}-{m:02d}"].values()]}
        for a, m in periodes
    ]
    return {"annee": annee, "mois": mois, "nb_mois": nb_mois,
            "clients": list(par_mois[f"{annee}-{mois:02d}"].values()),
            "historique": historique}


@app.get("/strategies/{symbol}/dashboard")
def dashboard(symbol: str, jours: int = Query(default=30, ge=1, le=3650)):
    """Relevés journaliers (table Dashboard) : capital, prix, gain du jour..."""
    depuis = (datetime.now(timezone.utc) - timedelta(days=jours)).strftime("%Y-%m-%d")
    return query(
        """SELECT Date AS date, Capital_graph AS capital, instant_price AS prix,
                  gain_day, epargne, Factu AS factu, tmp_UP AS up_tmp
           FROM Dashboard WHERE symbol = ? AND Date >= ? ORDER BY Date""",
        (symbol, depuis),
    )


@app.get("/logs")
def logs(
    type: str | None = Query(default="ERREUR", pattern="^(ERREUR|DEBUG)$"),
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=5000),
):
    """Derniers messages du journal du bot."""
    where, params = ["type = ?"], [type]
    if symbol:
        where.append("symbol = ?")
        params.append(symbol)
    params.append(limit)
    return query(
        "SELECT date, type, emplacement, erreur AS message, symbol FROM Log WHERE "
        + " AND ".join(where) + " ORDER BY date DESC LIMIT ?",
        params,
    )
