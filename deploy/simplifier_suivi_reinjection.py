"""Suivi des réinjections, version simplifiée (migration unique, 2026-11).

Remplace les colonnes de la version précédente (bénéfice / capital séparés) :
  supprimées : ecart_bet.reinj_benefice, ecart_bet.reinj_capital,
               ecart_bet.prix_moyen_capital, Devises.up_TMP_capital
  ajoutées   : ecart_bet.reinj_quantite    quantité réinjectée sur le palier
               ecart_bet.prix_moyen_reinj  prix moyen pondéré de cette quantité
               Devises.capital_injecte     total réinjecté au-delà du bénéfice
Le suivi repart de zéro (l'historique de l'ancienne version, de quelques jours,
n'est pas repris). Fonctionne aussi si l'ancienne migration n'a jamais été faite.

A lancer sur le serveur du bot, BOT ARRÊTÉ, AVANT de redémarrer le bot avec le
nouveau code :
    python3 deploy/simplifier_suivi_reinjection.py

- refuse de tourner si le bot tourne (verrou bot.lock pris) ;
- sauvegarde d'abord la base dans DB.db.avant_suivi_simplifie_<date> ;
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
    ("ecart_bet", "reinj_quantite", "REAL DEFAULT 0"),
    ("ecart_bet", "prix_moyen_reinj", "REAL"),
    ("Devises", "capital_injecte", "REAL DEFAULT 0"),
]
A_SUPPRIMER = [
    ("ecart_bet", "reinj_benefice"),
    ("ecart_bet", "reinj_capital"),
    ("ecart_bet", "prix_moyen_capital"),
    ("Devises", "up_TMP_capital"),
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
    ajouts = [c for c in A_AJOUTER if c[1] not in colonnes(con, c[0])]
    suppressions = [c for c in A_SUPPRIMER if c[1] in colonnes(con, c[0])]
    if not ajouts and not suppressions:
        print("Le suivi simplifié est déjà en place : rien à faire.")
        return
    avant = controle(con)

    sauvegarde = DB + ".avant_suivi_simplifie_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    with sqlite3.connect(sauvegarde) as dest:
        con.backup(dest)
    print(f"Sauvegarde : {sauvegarde}")

    for table, colonne, definition in ajouts:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
        print(f"  + {table}.{colonne}")
    con.commit()
    restantes = []
    for table, colonne in suppressions:
        try:
            con.execute(f"ALTER TABLE {table} DROP COLUMN {colonne}")
            print(f"  - {table}.{colonne}")
        except sqlite3.OperationalError as e:
            # SQLite < 3.35 : la colonne reste, sans effet (le code ne l'utilise plus)
            restantes.append(f"{table}.{colonne} ({e})")
    con.commit()

    apres = controle(con)
    manquantes = [c[1] for c in A_AJOUTER if c[1] not in colonnes(con, c[0])]
    if manquantes or apres != avant:
        sys.exit(f"ANOMALIE : colonnes manquantes {manquantes}, contrôle avant {avant}, après {apres}. "
                 f"Restaurer la sauvegarde : cp {sauvegarde} {DB}")
    if restantes:
        print("Colonnes anciennes laissées en place (inutilisées, sans risque) : " + ", ".join(restantes))
    print(f"Suivi simplifié en place. Contrôle OK : {apres[0][0]} paliers et {apres[1][0]} stratégies inchangés.")
    con.close()


if __name__ == "__main__":
    main()
