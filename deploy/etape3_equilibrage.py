"""Étape 3 : équilibrage du mode oscillation (migration unique, 2026-11).

Ajoute, sans rien modifier d'existant :
  Devises : equilibrage ('off' par défaut : comportement actuel), eq_distance (3
            paliers), eq_ecart (20 %), eq_seuil (15 €), eq_ordre_mini (6 €),
            eq_declenchement (30 %), eq_marge_plancher (1 €) ;
  journal_reinjection : colonnes eq_* (décision d'équilibrage de chaque vente) et
            up_epargne (part up versée en épargne : palier du dessus déjà à l'objectif).
Prérequis : migration de l'étape 2 (deploy/etape2_journal_reinjection.py).

A lancer sur le serveur du bot, BOT ARRÊTÉ, AVANT de redémarrer le bot avec le
nouveau code :
    python3 deploy/etape3_equilibrage.py

- refuse de tourner si le bot tourne (verrou bot.lock pris) ;
- sauvegarde d'abord la base dans DB.db.avant_etape3_<date> ;
- relançable sans risque (ne fait que ce qui reste à faire) ;
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

A_AJOUTER = [
    ("Devises", "equilibrage", "TEXT DEFAULT 'off'"),
    ("Devises", "eq_distance", "INTEGER DEFAULT 3"),
    ("Devises", "eq_ecart", "REAL DEFAULT 20"),
    ("Devises", "eq_seuil", "REAL DEFAULT 15"),
    ("Devises", "eq_ordre_mini", "REAL DEFAULT 6"),
    ("Devises", "eq_declenchement", "REAL DEFAULT 30"),
    ("Devises", "eq_marge_plancher", "REAL DEFAULT 1"),
    ("journal_reinjection", "eq_mode", "TEXT"),
    ("journal_reinjection", "eq_applique", "INTEGER"),
    ("journal_reinjection", "eq_raison", "TEXT"),
    ("journal_reinjection", "eq_cible", "INTEGER"),
    ("journal_reinjection", "eq_gain_cible_avant", "REAL"),
    ("journal_reinjection", "eq_gain_cible_apres", "REAL"),
    ("journal_reinjection", "eq_preteur", "INTEGER"),
    ("journal_reinjection", "eq_position", "TEXT"),
    ("journal_reinjection", "eq_gain_preteur_avant", "REAL"),
    ("journal_reinjection", "eq_gain_preteur_apres", "REAL"),
    ("journal_reinjection", "eq_q", "REAL"),
    ("journal_reinjection", "eq_cout", "REAL"),
    ("journal_reinjection", "eq_vertical", "REAL"),
    ("journal_reinjection", "eq_ordre", "TEXT"),
    ("journal_reinjection", "up_epargne", "REAL"),
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
    if not colonnes(con, "journal_reinjection"):
        sys.exit("Table journal_reinjection absente : lancer d'abord deploy/etape2_journal_reinjection.py")
    ajouts = [c for c in A_AJOUTER if c[1] not in colonnes(con, c[0])]
    if not ajouts:
        print("L'étape 3 est déjà en place : rien à faire.")
        return
    avant = controle(con)
    sauvegarde = DB + ".avant_etape3_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    with sqlite3.connect(sauvegarde) as dest:
        con.backup(dest)
    print(f"Sauvegarde : {sauvegarde}")
    for table, colonne, definition in ajouts:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
        print(f"  + {table}.{colonne}")
    con.commit()
    apres = controle(con)
    manquantes = [c[1] for c in A_AJOUTER if c[1] not in colonnes(con, c[0])]
    if manquantes or apres != avant:
        sys.exit(f"ANOMALIE : manquants {manquantes}, contrôle avant {avant}, après {apres}. "
                 f"Restaurer la sauvegarde : cp {sauvegarde} {DB}")
    print(f"Étape 3 en place (équilibrage : off partout). Contrôle OK : "
          f"{apres[0][0]} paliers et {apres[1][0]} stratégies inchangés.")
    con.close()


if __name__ == "__main__":
    main()
