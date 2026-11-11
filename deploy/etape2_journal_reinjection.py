"""Étape 2 : journal du wallet, journal des réinjections, source de réinjection (migration unique, 2026-11).

  1. exporte ecart_bet.reinj_quantite et prix_moyen_reinj dans un CSV daté
     (export_reinjection_<date>.csv à côté de DB.db), puis supprime ces colonnes ;
  2. crée les tables journal_wallet et journal_reinjection (ajout de lignes uniquement) ;
  3. ajoute à Devises : source_reinjection ('EUR' par défaut = comportement
     actuel), ecart_min_ma (0), si_reserves_insuffisantes ('suspendre'),
     reinjection_suspendue (date de la suspension en cours, ou NULL).

A lancer sur le serveur du bot, BOT ARRÊTÉ, AVANT de redémarrer le bot avec le
nouveau code :
    python3 deploy/etape2_journal_reinjection.py

- refuse de tourner si le bot tourne (verrou bot.lock pris) ;
- sauvegarde d'abord la base dans DB.db.avant_etape2_<date> ;
- relançable sans risque (ne fait que ce qui reste à faire) ;
- vérifie que la grille et les stratégies sont inchangées.
"""
import csv
import fcntl
import os
import sqlite3
import sys
from datetime import datetime

BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BOT_DIR, "DB.db")
LOCK = os.path.join(BOT_DIR, "bot.lock")

A_SUPPRIMER = [("ecart_bet", "reinj_quantite"), ("ecart_bet", "prix_moyen_reinj")]
A_AJOUTER = [
    ("Devises", "source_reinjection", "TEXT DEFAULT 'EUR'"),
    ("Devises", "ecart_min_ma", "REAL DEFAULT 0"),
    ("Devises", "si_reserves_insuffisantes", "TEXT DEFAULT 'suspendre'"),
    ("Devises", "reinjection_suspendue", "TEXT"),
]
TABLES = {
    "journal_wallet": """CREATE TABLE journal_wallet (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        date            TEXT NOT NULL,   -- ISO UTC, après l'exécution
        symbol          TEXT NOT NULL,
        id_client       INTEGER,
        ordre_id        TEXT,            -- identifiant Binance
        sens            TEXT,            -- BUY / SELL
        type_ordre      TEXT,            -- LIMIT / MARKET
        motif           TEXT,            -- grille, up, financement, solde partiel
        palier          INTEGER,
        prix_execution  REAL,
        quantite        REAL,            -- quantité d'actif exécutée
        prix_marche     REAL,            -- prix de la paire à l'enregistrement
        wallet_devise2  REAL,            -- cotation (EUR) libre + bloquée
        wallet_devise1  REAL,            -- actif (PEPE) libre + bloqué
        valeur_wallet   REAL,            -- devise2 + devise1 × prix_marche
        reserve_devise2 REAL,
        reserve_devise1 REAL,
        erreur          TEXT             -- lecture du wallet impossible : champs du wallet vides
    )""",
    "journal_reinjection": """CREATE TABLE journal_reinjection (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        date               TEXT NOT NULL,
        symbol             TEXT NOT NULL,
        ordre_vente        TEXT,          -- ordre LIMIT d'origine
        benefice           REAL,          -- B
        taux_local         REAL, taux_up REAL, taux_down REAL,   -- en %
        local              REAL, up REAL, down REAL,             -- montants en cotation
        mode               TEXT,          -- EUR / observation / auto
        simulee            INTEGER,       -- 1 : décision qu'aurait prise le mode auto (observation)
        source             TEXT,          -- EUR / PEPE / SUSPENDU
        raison             TEXT,
        ma7                REAL, ma25 REAL, ma_bougie TEXT,
        prix_marche        REAL,
        reserve_devise2    REAL,          -- réserves juste après la vente
        reserve_devise1    REAL,
        palier_local       INTEGER, qte_local REAL,
        palier_down        INTEGER, qte_down REAL,
        qte_devise1_vendue REAL,          -- vente de financement (ou qui aurait été faite)
        prix_financement   REAL,
        ordre_financement  TEXT,
        capital_injecte    REAL,          -- part capital, en cotation
        up_tmp_avant       REAL, up_tmp_apres REAL
    )""",
}
INDEX = ["CREATE INDEX IF NOT EXISTS journal_wallet_symbol_date ON journal_wallet (symbol, date)",
         "CREATE INDEX IF NOT EXISTS journal_reinjection_symbol_date ON journal_reinjection (symbol, date)"]


def bot_arrete():
    """Vrai si aucun trader.py ne tient le verrou bot.lock."""
    if not os.path.exists(LOCK):
        return True
    with open(LOCK, "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
            return True
        except BlockingIOError:
            return False


def colonnes(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def tables(con):
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def controle(con):
    return (con.execute("SELECT COUNT(*), ROUND(SUM(bet), 6), ROUND(SUM(prix), 12) FROM ecart_bet").fetchone(),
            con.execute("SELECT COUNT(*), ROUND(SUM(benef_all), 6), ROUND(SUM(up_TMP), 9) FROM Devises").fetchone())


def main():
    if not os.path.exists(DB):
        sys.exit(f"Base introuvable : {DB}")
    if not bot_arrete():
        sys.exit("Le bot tourne (bot.lock verrouillé) : l'arrêter d'abord (bouton Éteindre ou krypto-bot.sh choix 6).")
    con = sqlite3.connect(DB, timeout=30)
    suppressions = [c for c in A_SUPPRIMER if c[1] in colonnes(con, c[0])]
    ajouts = [c for c in A_AJOUTER if c[1] not in colonnes(con, c[0])]
    a_creer = [t for t in TABLES if t not in tables(con)]
    if not suppressions and not ajouts and not a_creer:
        print("L'étape 2 est déjà en place : rien à faire.")
        return
    avant = controle(con)
    date = datetime.now().strftime("%Y%m%d_%H%M%S")

    sauvegarde = DB + ".avant_etape2_" + date
    with sqlite3.connect(sauvegarde) as dest:
        con.backup(dest)
    print(f"Sauvegarde : {sauvegarde}")

    if suppressions:
        presentes = [c[1] for c in suppressions]
        lignes = con.execute(f"SELECT symbol, ID, prix, bet, {', '.join(presentes)} FROM ecart_bet "
                             "ORDER BY symbol, ID").fetchall()
        fichier = os.path.join(BOT_DIR, f"export_reinjection_{date}.csv")
        with open(fichier, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["symbol", "ID", "prix", "bet"] + presentes)
            w.writerows(lignes)
        with open(fichier, newline="") as f:
            relues = sum(1 for _ in csv.reader(f, delimiter=";")) - 1
        if relues != len(lignes):
            sys.exit(f"ANOMALIE : export incomplet ({relues} lignes relues sur {len(lignes)}). Rien n'a été supprimé.")
        print(f"Export : {fichier} ({relues} paliers, dont "
              f"{sum(1 for l in lignes if l[4]) } avec une quantité réinjectée)")

    for table, colonne, definition in ajouts:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
        print(f"  + {table}.{colonne}")
    for t in a_creer:
        con.execute(TABLES[t])
        print(f"  + table {t}")
    for i in INDEX:
        con.execute(i)
    con.commit()
    restantes = []
    for table, colonne in suppressions:
        try:
            con.execute(f"ALTER TABLE {table} DROP COLUMN {colonne}")
            print(f"  - {table}.{colonne}")
        except sqlite3.OperationalError as e:
            restantes.append(f"{table}.{colonne} ({e})")
    con.commit()

    apres = controle(con)
    manquantes = ([c[1] for c in A_AJOUTER if c[1] not in colonnes(con, c[0])]
                  + [t for t in TABLES if t not in tables(con)])
    if manquantes or apres != avant:
        sys.exit(f"ANOMALIE : manquants {manquantes}, contrôle avant {avant}, après {apres}. "
                 f"Restaurer la sauvegarde : cp {sauvegarde} {DB}")
    if restantes:
        print("Colonnes laissées en place (plus lues ni écrites, sans risque) : " + ", ".join(restantes))
    print(f"Étape 2 en place (source de réinjection : EUR partout). Contrôle OK : "
          f"{apres[0][0]} paliers et {apres[1][0]} stratégies inchangés.")
    con.close()


if __name__ == "__main__":
    main()
