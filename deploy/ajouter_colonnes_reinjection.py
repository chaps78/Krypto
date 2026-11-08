"""Ajoute les colonnes de suivi des réinjections dans DB.db (migration unique, 2026-11).

  ecart_bet.reinj_benefice      quantité réinjectée sur le palier venant du bénéfice
  ecart_bet.reinj_capital       quantité réinjectée venant du capital (au-delà de 100 %)
  ecart_bet.prix_moyen_capital  prix moyen pondéré de la quantité venant du capital
  Devises.up_TMP_capital        part de up_TMP venant du capital (en attente d'achat)

A lancer sur le serveur du bot, BOT ARRÊTÉ, AVANT de redémarrer le bot avec le
nouveau code :
    python3 deploy/ajouter_colonnes_reinjection.py

- refuse de tourner si le bot tourne (verrou bot.lock pris) ;
- sauvegarde d'abord la base dans DB.db.avant_colonnes_reinjection_<date> ;
- n'ajoute que les colonnes absentes (relançable sans risque) ;
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

COLONNES = [
    ("ecart_bet", "reinj_benefice", "REAL DEFAULT 0"),
    ("ecart_bet", "reinj_capital", "REAL DEFAULT 0"),
    ("ecart_bet", "prix_moyen_capital", "REAL"),
    ("Devises", "up_TMP_capital", "REAL DEFAULT 0"),
]


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


def controle(con):
    return (con.execute("SELECT COUNT(*), ROUND(SUM(bet), 6), ROUND(SUM(prix), 12) FROM ecart_bet").fetchone(),
            con.execute("SELECT COUNT(*), ROUND(SUM(benef_all), 6), ROUND(SUM(up_TMP), 9) FROM Devises").fetchone())


def main():
    if not os.path.exists(DB):
        sys.exit(f"Base introuvable : {DB}")
    if not bot_arrete():
        sys.exit("Le bot tourne (bot.lock verrouillé) : l'arrêter d'abord (bouton Éteindre ou krypto-bot.sh choix 6).")
    con = sqlite3.connect(DB, timeout=30)
    a_ajouter = [c for c in COLONNES if c[1] not in colonnes(con, c[0])]
    if not a_ajouter:
        print("Les colonnes de suivi des réinjections existent déjà : rien à faire.")
        return
    avant = controle(con)

    sauvegarde = DB + ".avant_colonnes_reinjection_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    with sqlite3.connect(sauvegarde) as dest:
        con.backup(dest)
    print(f"Sauvegarde : {sauvegarde}")

    for table, colonne, definition in a_ajouter:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
        print(f"  + {table}.{colonne}")
    con.commit()

    apres = controle(con)
    manquantes = [c[1] for c in COLONNES if c[1] not in colonnes(con, c[0])]
    if manquantes or apres != avant:
        sys.exit(f"ANOMALIE : colonnes manquantes {manquantes}, contrôle avant {avant}, après {apres}. "
                 f"Restaurer la sauvegarde : cp {sauvegarde} {DB}")
    print(f"Colonnes ajoutées. Contrôle OK : {apres[0][0]} paliers et {apres[1][0]} stratégies inchangés.")
    con.close()


if __name__ == "__main__":
    main()
