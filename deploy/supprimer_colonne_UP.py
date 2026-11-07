"""Supprime la colonne ecart_bet.UP de DB.db (migration unique, 2026-11).

L'ancien mécanisme UP par palier a été retiré du code ; sa colonne ne sert plus.
A lancer sur le serveur du bot, BOT ARRÊTÉ :
    python3 deploy/supprimer_colonne_UP.py

- refuse de tourner si le bot tourne (verrou bot.lock pris) ;
- sauvegarde d'abord la base dans DB.db.avant_suppression_UP_<date> ;
- ne fait rien si la colonne est déjà absente ;
- vérifie ensuite que le nombre de paliers et la somme des bets sont inchangés.
"""
import fcntl
import os
import sqlite3
import sys
from datetime import datetime

BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BOT_DIR, "DB.db")
LOCK = os.path.join(BOT_DIR, "bot.lock")


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


def colonnes(con):
    return [r[1] for r in con.execute("PRAGMA table_info(ecart_bet)")]


def controle(con):
    return con.execute("SELECT COUNT(*), ROUND(SUM(bet), 6), ROUND(SUM(prix), 12) FROM ecart_bet").fetchone()


def main():
    if not os.path.exists(DB):
        sys.exit(f"Base introuvable : {DB}")
    if not bot_arrete():
        sys.exit("Le bot tourne (bot.lock verrouillé) : l'arrêter d'abord (bouton Éteindre ou krypto-bot.sh choix 6).")
    con = sqlite3.connect(DB, timeout=30)
    if "UP" not in colonnes(con):
        print("La colonne ecart_bet.UP n'existe déjà plus : rien à faire.")
        return
    avant = controle(con)

    sauvegarde = DB + ".avant_suppression_UP_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    with sqlite3.connect(sauvegarde) as dest:
        con.backup(dest)
    print(f"Sauvegarde : {sauvegarde}")

    if sqlite3.sqlite_version_info >= (3, 35, 0):
        con.execute("ALTER TABLE ecart_bet DROP COLUMN UP")
        con.commit()
    else:  # SQLite trop ancien pour DROP COLUMN : reconstruction de la table
        con.executescript("""
            BEGIN;
            CREATE TABLE ecart_bet_nouveau ("ID" INTEGER, "symbol" TEXT, "prix" REAL, "bet" REAL,
                                            PRIMARY KEY("ID","symbol"));
            INSERT INTO ecart_bet_nouveau (ID, symbol, prix, bet) SELECT ID, symbol, prix, bet FROM ecart_bet;
            DROP TABLE ecart_bet;
            ALTER TABLE ecart_bet_nouveau RENAME TO ecart_bet;
            COMMIT;
        """)

    apres = controle(con)
    if "UP" in colonnes(con) or apres != avant:
        sys.exit(f"ANOMALIE : contrôle avant {avant}, après {apres}. Restaurer la sauvegarde : cp {sauvegarde} {DB}")
    print(f"Colonne ecart_bet.UP supprimée. Contrôle OK : {apres[0]} paliers, somme des bets inchangée.")
    print("Colonnes restantes :", ", ".join(colonnes(con)))
    con.close()


if __name__ == "__main__":
    main()
