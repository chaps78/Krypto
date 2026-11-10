"""Tables de suivi des réserves et des moyennes mobiles (migration unique, 2026-11).

Ajoute deux tables, sans toucher aux tables existantes :
  reserves          une ligne par stratégie active et par heure : prix, palier
                    courant, solde / besoin de la grille / réserve en devise de
                    cotation (devise2, EUR) et en actif (devise1, PEPE), et la
                    valeur de la réserve d'actif en devise de cotation ;
  moyennes_mobiles  MA7 et MA25 des bougies 1h terminées, par paire Binance
                    (une ligne par bougie, sans doublon).
Elles sont remplies par l'API (tâche horaire), jamais lues par le bot.

A lancer sur le serveur du bot, BOT ARRÊTÉ, avant de redémarrer l'API :
    python3 deploy/ajouter_tables_reserves_ma.py

- refuse de tourner si le bot tourne (verrou bot.lock pris) ;
- sauvegarde d'abord la base dans DB.db.avant_reserves_ma_<date> ;
- relançable sans risque (ne crée que ce qui manque) ;
- vérifie que la grille et les stratégies sont inchangées.
"""
import fcntl
import os
import sqlite3
import sys
from datetime import datetime

BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BOT_DIR, "DB.db")
LOCK = os.path.join(BOT_DIR, "bot.lock")

TABLES = {
    "reserves": """CREATE TABLE reserves (
        date                   TEXT NOT NULL,   -- ISO UTC
        symbol                 TEXT NOT NULL,   -- stratégie (Devises.symbol)
        prix                   REAL,            -- prix Binance de la paire
        palier                 INTEGER,         -- palier du dernier ordre LIMIT exécuté
        wallet_devise2         REAL,            -- solde cotation (libre + bloqué)
        grille_devise2         REAL,            -- somme bet × prix sous le palier
        reserve_devise2        REAL,            -- wallet − grille
        wallet_devise1         REAL,            -- solde actif (libre + bloqué)
        grille_devise1         REAL,            -- somme des bets à partir du palier
        reserve_devise1        REAL,            -- wallet − grille
        reserve_devise1_valeur REAL             -- reserve_devise1 × prix
    )""",
    "moyennes_mobiles": """CREATE TABLE moyennes_mobiles (
        paire       TEXT NOT NULL,   -- ex. PEPEEUR
        intervalle  TEXT NOT NULL,   -- 1h
        ouverture   TEXT NOT NULL,   -- ouverture de la bougie, ISO UTC
        cloture     REAL,            -- prix de clôture de la bougie
        ma7         REAL,
        ma25        REAL,
        calcule_le  TEXT,            -- ISO UTC
        PRIMARY KEY (paire, intervalle, ouverture)
    )""",
}
INDEX = "CREATE INDEX IF NOT EXISTS reserves_symbol_date ON reserves (symbol, date)"


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
    a_creer = [t for t in TABLES if t not in tables(con)]
    if not a_creer:
        con.execute(INDEX)
        con.commit()
        print("Les tables reserves et moyennes_mobiles existent déjà : rien à faire.")
        return
    avant = controle(con)

    sauvegarde = DB + ".avant_reserves_ma_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    with sqlite3.connect(sauvegarde) as dest:
        con.backup(dest)
    print(f"Sauvegarde : {sauvegarde}")

    for t in a_creer:
        con.execute(TABLES[t])
        print(f"  + table {t}")
    con.execute(INDEX)
    con.commit()

    apres = controle(con)
    manquantes = [t for t in TABLES if t not in tables(con)]
    if manquantes or apres != avant:
        sys.exit(f"ANOMALIE : tables manquantes {manquantes}, contrôle avant {avant}, après {apres}. "
                 f"Restaurer la sauvegarde : cp {sauvegarde} {DB}")
    print(f"Tables en place. Contrôle OK : {apres[0][0]} paliers et {apres[1][0]} stratégies inchangés.")
    con.close()


if __name__ == "__main__":
    main()
