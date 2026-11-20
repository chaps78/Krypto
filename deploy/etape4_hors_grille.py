"""4.6 : suivi du capital hors de la grille. Migration, 2026-11.

Ajoute deux colonnes à journal_reinjection, sans rien modifier d'existant :
  hors_grille       : effet de la vente sur le capital hors de la grille, en euros
                      (+ bénéfice non réinjecté, − capital pris dans la réserve, part
                      financée en PEPE comptée au prix d'exécution) ;
  cumul_hors_grille : cumul par stratégie, à partir de 0 à la première vente suivante.
Les lignes déjà présentes restent vides : le suivi commence au redémarrage du bot.

A lancer sur le serveur du bot, BOT ARRÊTÉ, AVANT de redémarrer le bot avec le
nouveau code :
    python3 deploy/etape4_hors_grille.py

- refuse de tourner si le bot tourne (verrou bot.lock pris) ;
- sauvegarde d'abord la base dans DB.db.avant_hors_grille_<date> ;
- relançable sans risque ;
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
    ("journal_reinjection", "hors_grille", "REAL"),
    ("journal_reinjection", "cumul_hors_grille", "REAL"),
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
            con.execute("SELECT COUNT(*), ROUND(SUM(benef_all), 6), ROUND(SUM(up_TMP), 9) FROM Devises").fetchone(),
            con.execute("SELECT COUNT(*) FROM journal_reinjection").fetchone())


def main():
    if not os.path.exists(DB):
        sys.exit(f"Base introuvable : {DB}")
    if not bot_arrete():
        sys.exit("Le bot tourne (bot.lock verrouillé) : l'arrêter d'abord (bouton Éteindre ou krypto-bot.sh choix 6).")
    con = sqlite3.connect(DB, timeout=30)
    if "tr_sources" not in colonnes(con, "journal_reinjection"):
        sys.exit("Étape 4 incomplète : lancer d'abord deploy/etape4_translation.py")
    ajouts = [c for c in A_AJOUTER if c[1] not in colonnes(con, c[0])]
    if not ajouts:
        print("Le suivi hors grille (4.6) est déjà en place : rien à faire.")
        return
    avant = controle(con)
    sauvegarde = DB + ".avant_hors_grille_" + datetime.now().strftime("%Y%m%d_%H%M%S")
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
    print(f"Suivi hors grille en place (démarre à la prochaine vente). Contrôle OK : "
          f"{apres[0][0]} paliers, {apres[1][0]} stratégies, {apres[2][0]} lignes de journal inchangés.")
    con.close()


if __name__ == "__main__":
    main()
