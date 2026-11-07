"""API HTTP du bot, destinée au front (accès via tunnel SSH).

Lecture seule sur DB.db. Seule action possible : arrêter ou démarrer le
service krypto-bot (POST /bot/arreter et /bot/demarrer), via sudo limité à
ces deux commandes (deploy/krypto-bot.sudoers).

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
    KRYPTO_CLES_LECTURE  fichier des clés Binance EN LECTURE SEULE utilisées
                      pour /wallets (défaut : cles_lecture.json à côté).
                      Jamais les clés de trading du bot : voir
                      deploy/cles_lecture.json.example.

Documentation interactive : http://127.0.0.1:8000/docs
"""
import hashlib
import hmac
import json
import os
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query

import reinjection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("KRYPTO_DB", os.path.join(BASE_DIR, "DB.db"))
API_TOKEN = os.environ.get("KRYPTO_API_TOKEN")
HEARTBEAT = os.environ.get("KRYPTO_HEARTBEAT", os.path.join(BASE_DIR, "bot.heartbeat"))
BOT_DELAI = int(os.environ.get("KRYPTO_BOT_DELAI", "180"))
CLES_LECTURE = os.environ.get("KRYPTO_CLES_LECTURE", os.path.join(BASE_DIR, "cles_lecture.json"))


def check_token(authorization: str | None = Header(default=None)):
    """Vérifie l'en-tête Authorization si KRYPTO_API_TOKEN est défini."""
    if API_TOKEN and authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Token invalide")


@asynccontextmanager
async def demarrage(app):
    """Précharge prix et portefeuilles en arrière-plan dès le démarrage de l'API."""
    def precharger():
        try:
            prix_actuels()
            en_cache("wallets", calculer_wallets)
        except Exception as e:
            print(f"Préchargement des portefeuilles impossible : {e}")
    threading.Thread(target=precharger, daemon=True).start()
    yield


app = FastAPI(title="Krypto API", version="1.0", dependencies=[Depends(check_token)], lifespan=demarrage)


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


SYSTEMCTL = "/usr/bin/systemctl"


def piloter_bot(action):
    """Lance "systemctl --no-block <action> krypto-bot" via sudo sans mot de passe.

    --no-block : la commande rend la main tout de suite ; l'arrêt propre du bot
    (fin de la stratégie en cours) peut ensuite prendre jusqu'à 2 min.
    """
    try:
        r = subprocess.run(["sudo", "-n", SYSTEMCTL, "--no-block", action, "krypto-bot"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as e:
        raise HTTPException(status_code=500, detail=f"Commande impossible : {e}")
    if r.returncode != 0:
        erreur = (r.stderr or r.stdout).strip()
        if "password" in erreur or "mot de passe" in erreur:
            erreur = ("droits sudo manquants sur le serveur du bot : "
                      "installer la règle avec deploy/krypto-bot.sh (choix 10)")
        raise HTTPException(status_code=500, detail=f"{action} impossible : {erreur}")


@app.post("/bot/arreter", status_code=202)
def arreter_bot():
    """Demande l'arrêt propre du bot (service krypto-bot)."""
    etat = bot()
    if etat["service"] not in ("active", "activating", "reloading"):
        raise HTTPException(status_code=409, detail="Le service krypto-bot n'est pas en marche"
                            + (" (bot lancé à la main ?)" if etat["en_marche"] else ""))
    piloter_bot("stop")
    return {"demande": "arret"}


@app.post("/bot/demarrer", status_code=202)
def demarrer_bot():
    """Démarre le bot (service krypto-bot), s'il ne tourne pas déjà."""
    etat = bot()
    if etat["service"] in ("active", "activating", "reloading", "deactivating"):
        raise HTTPException(status_code=409, detail=f"Le service krypto-bot est déjà « {etat['service']} »")
    if etat["en_marche"]:
        raise HTTPException(status_code=409, detail="Un bot tourne déjà hors du service (lancé à la main)")
    piloter_bot("start")
    return {"demande": "demarrage"}


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


@app.get("/reinjection")
def bareme_reinjection():
    """Barèmes des parts "local" et "up" : taux (%) selon le bénéfice d'une vente.

    Chaque tranche : {"jusqua": seuil exclu (None = au-delà du dernier), "taux": %}.
    """
    def tranches(bareme, defaut):
        return [{"jusqua": s, "taux": t} for s, t in bareme] + [{"jusqua": None, "taux": defaut}]
    return {"local": tranches(reinjection.BAREME_LOCAL, reinjection.DEFAUT_LOCAL),
            "up": tranches(reinjection.BAREME_UP, reinjection.DEFAUT_UP)}


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
    actuel (liste de prix publique partagée, en cache). Mois en cours par défaut.
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
    prix = prix_actuels()
    for l in lignes:
        clients = par_mois.get(l["periode"])
        if clients is None:
            continue
        c = clients.setdefault(l["id_client"], {
            "id_client": l["id_client"], "nom": l["nom"], "base": l["base"],
            "total": 0.0, "complet": True, "strategies": []})
        taux = valeur_en(l["devise"], l["base"], prix)
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


###########################################################################
#                    PORTEFEUILLES (clés en lecture seule)                #
###########################################################################
BINANCE = "https://api.binance.com"
CACHE_DUREE = 60  # secondes avant de rafraîchir (en arrière-plan) prix et portefeuilles
_cache = {}                     # cle -> (date, valeur)
_en_cours = set()               # clés en cours de rafraîchissement
_verrou = threading.Lock()


def _rafraichir(cle, fonction):
    """Recalcule une valeur du cache ; en cas d'échec, l'ancienne valeur est gardée."""
    try:
        valeur = fonction()
        with _verrou:
            _cache[cle] = (time.time(), valeur)
    except Exception as e:  # Binance injoignable, clé refusée... : on réessaiera
        print(f"Cache {cle} : rafraîchissement impossible : {e}")
    finally:
        with _verrou:
            _en_cours.discard(cle)


def en_cache(cle, fonction):
    """Valeur en cache, sans jamais faire attendre si une valeur existe déjà.

    - aucune valeur : calcul immédiat (seul cas où l'appelant attend Binance) ;
    - valeur de plus de CACHE_DUREE s : elle est renvoyée telle quelle et un
      rafraîchissement est lancé en arrière-plan pour l'appel suivant.
    """
    with _verrou:
        present = _cache.get(cle)
        lancer = (present is not None and time.time() - present[0] >= CACHE_DUREE
                  and cle not in _en_cours)
        if lancer:
            _en_cours.add(cle)
    if present is None:
        valeur = fonction()
        with _verrou:
            _cache[cle] = (time.time(), valeur)
        return valeur
    if lancer:
        threading.Thread(target=_rafraichir, args=(cle, fonction), daemon=True).start()
    return present[1]


def tous_les_prix():
    """Tous les prix Binance en un appel (route publique) : {"BTCEUR": 61234.5, ...}."""
    with urllib.request.urlopen(BINANCE + "/api/v3/ticker/price", timeout=10) as resp:
        return {p["symbol"]: float(p["price"]) for p in json.load(resp)}


def prix_actuels():
    """Liste de prix partagée (cache), ou {} si Binance est injoignable."""
    try:
        return en_cache("prix", tous_les_prix)
    except (OSError, ValueError) as e:
        print(f"Prix Binance indisponibles : {e}")
        return {}


def valeur_en(actif, cible, prix):
    """Prix d'une unité d'actif dans la devise cible, ou None.

    Paire directe, sinon inverse, sinon en passant par USDT puis BTC.
    Les actifs « LDxxx » (Simple Earn flexible) valent l'actif xxx.
    """
    def direct(a, b):
        if a == b:
            return 1.0
        if a + b in prix:
            return prix[a + b]
        if b + a in prix and prix[b + a]:
            return 1 / prix[b + a]
        return None

    for a in ([actif, actif[2:]] if actif.startswith("LD") else [actif]):
        v = direct(a, cible)
        if v is not None:
            return v
        for pivot in ("USDT", "BTC"):
            v1, v2 = direct(a, pivot), direct(pivot, cible)
            if v1 is not None and v2 is not None:
                return v1 * v2
    return None


def compte_binance(api, secret):
    """Soldes non nuls d'un compte spot (GET /api/v3/account, requête signée).

    Lecture seule : seule cette route est appelée, avec une clé qui ne doit
    avoir que le droit « Enable Reading ».
    """
    params = urllib.parse.urlencode({"omitZeroBalances": "true", "recvWindow": 10000,
                                     "timestamp": int(time.time() * 1000)})
    signature = hmac.new(secret.encode(), params.encode(), hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"{BINANCE}/api/v3/account?{params}&signature={signature}",
                                 headers={"X-MBX-APIKEY": api})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)["balances"]
    except urllib.error.HTTPError as e:
        try:
            detail = json.load(e).get("msg", "")
        except ValueError:
            detail = ""
        raise RuntimeError(f"Binance a refusé ({e.code}) {detail}".strip()) from e


def lire_cles():
    """Clés en lecture seule par ID_client, depuis CLES_LECTURE ({} si absent)."""
    if not os.path.exists(CLES_LECTURE):
        return {}
    with open(CLES_LECTURE) as f:
        return {int(k): v for k, v in json.load(f).items()}


def calculer_wallets():
    """Soldes de chaque compte configuré, valorisés en EUR et en USDT."""
    try:
        cles = lire_cles()
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"{os.path.basename(CLES_LECTURE)} illisible : {e}")
    if not cles:
        return {"configure": False, "comptes": [], "total_eur": 0.0, "total_usdt": 0.0, "complet": True}
    noms = {c["ID_client"]: c["nom"] for c in query("SELECT ID_client, nom FROM client")}
    prix = prix_actuels()
    if not prix:
        raise HTTPException(status_code=502, detail="Prix Binance indisponibles")
    comptes = []
    for id_client, cle in sorted(cles.items()):
        compte = {"id_client": id_client, "nom": noms.get(id_client, f"client {id_client}"),
                  "erreur": None, "actifs": [], "total_eur": 0.0, "total_usdt": 0.0, "complet": True}
        try:
            soldes = compte_binance(cle["api"], cle["secret"])
        except (RuntimeError, OSError, KeyError, ValueError) as e:
            compte["erreur"] = str(e)
            compte["complet"] = False
            comptes.append(compte)
            continue
        for b in soldes:
            libre, bloque = float(b["free"]), float(b["locked"])
            total = libre + bloque
            if total <= 0:
                continue
            eur, usdt = valeur_en(b["asset"], "EUR", prix), valeur_en(b["asset"], "USDT", prix)
            actif = {"actif": b["asset"], "libre": libre, "bloque": bloque, "total": total,
                     "eur": total * eur if eur is not None else None,
                     "usdt": total * usdt if usdt is not None else None}
            if actif["eur"] is None or actif["usdt"] is None:
                compte["complet"] = False
            compte["total_eur"] += actif["eur"] or 0.0
            compte["total_usdt"] += actif["usdt"] or 0.0
            compte["actifs"].append(actif)
        compte["actifs"].sort(key=lambda a: a["eur"] or 0.0, reverse=True)
        comptes.append(compte)
    return {
        "configure": True,
        "maj": datetime.now(timezone.utc).isoformat(),
        "comptes": comptes,
        "total_eur": sum(c["total_eur"] for c in comptes),
        "total_usdt": sum(c["total_usdt"] for c in comptes),
        "complet": all(c["complet"] for c in comptes),
    }


@app.get("/wallets")
def wallets():
    """Portefeuilles spot des comptes ayant une clé en lecture seule configurée.

    Pour chaque compte : actifs (libre, bloqué dans des ordres, total) valorisés
    en EUR et en USDT au prix Binance actuel, et totaux. Réponse immédiate
    depuis le cache, rafraîchi en arrière-plan toutes les 60 s au plus
    (Binance limite les appels, partagés avec le bot sur cette IP) ; "maj"
    donne l'heure des données. Préchargé au démarrage de l'API.
    configure=false si le fichier de clés est absent ou vide.
    """
    return en_cache("wallets", calculer_wallets)


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
