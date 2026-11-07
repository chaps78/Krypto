"""Supprime la table Dashboard de DB.db (migration unique, 2026-11).

Relevés quotidiens écrits par l'ancien rapport "KPI.py day", arrêté depuis
juillet 2026 ; plus aucun code ne l'utilise. A lancer sur le serveur du bot, BOT ARRÊTÉ :
    python3 deploy/supprimer_table_dashboard.py

- refuse de tourner si le bot tourne (verrou bot.lock pris) ;
- sauvegarde d'abord la base dans DB.db.avant_suppression_dashboard_<date> ;
- ne fait rien si la table est déjà absente ;
- vérifie ensuite que la grille (ecart_bet) est inchangée.
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


def table_existe(con):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='Dashboard'").fetchone() is not None


def controle(con):
    return con.execute("SELECT COUNT(*), ROUND(SUM(bet), 6), ROUND(SUM(prix), 12) FROM ecart_bet").fetchone()


def main():
    if not os.path.exists(DB):
        sys.exit(f"Base introuvable : {DB}")
    if not bot_arrete():
        sys.exit("Le bot tourne (bot.lock verrouillé) : l'arrêter d'abord (bouton Éteindre ou krypto-bot.sh choix 6).")
    con = sqlite3.connect(DB, timeout=30)
    if not table_existe(con):
        print("La table Dashboard n'existe déjà plus : rien à faire.")
        return
    avant = controle(con)
    lignes = con.execute("SELECT COUNT(*) FROM Dashboard").fetchone()[0]

    sauvegarde = DB + ".avant_suppression_dashboard_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    with sqlite3.connect(sauvegarde) as dest:
        con.backup(dest)
    print(f"Sauvegarde : {sauvegarde}")

    con.execute("DROP TABLE Dashboard")
    con.commit()

    apres = controle(con)
    if table_existe(con) or apres != avant:
        sys.exit(f"ANOMALIE : contrôle avant {avant}, après {apres}. Restaurer la sauvegarde : cp {sauvegarde} {DB}")
    print(f"Table Dashboard supprimée ({lignes} lignes). Grille inchangée : {apres[0]} paliers.")
    con.close()


if __name__ == "__main__":
    main()
