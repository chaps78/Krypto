"""Suivi des réinjections, version simplifiée (migration unique, 2026-11).

Remplace les colonnes de la version précédente (bénéfice / capital séparés) :
  supprimées : ecart_bet.reinj_benefice, ecart_bet.reinj_capital,
               ecart_bet.prix_moyen_capital, Devises.up_TMP_capital
  ajoutées   : ecart_bet.reinj_quantite    quantité réinjectée sur le palier
               ecart_bet.prix_moyen_reinj  prix moyen pondéré de cette quantité
               Devises.capital_injecte     total réinjecté au-delà du bénéfice
Reprise des valeurs de l'ancienne version (avant suppression des colonnes) :
  reinj_quantite   = reinj_benefice + reinj_capital
  prix_moyen_reinj = prix_moyen_capital s'il existe (local, down et UP mettaient
                     bénéfice et capital au même prix à chaque réinjection),
                     sinon le prix du palier (réinjections locales/down)
  capital_injecte  = somme des reinj_capital × prix_moyen_capital + up_TMP_capital
Fonctionne aussi si l'ancienne migration n'a jamais été faite (rien à reprendre).

Si cette migration a déjà été lancée SANS reprise (première version du script),
reprendre les valeurs depuis la sauvegarde qu'elle a créée (ajoutées à ce que le
bot a suivi depuis ; une seule fois, bot arrêté) :
    python3 deploy/simplifier_suivi_reinjection.py --reprendre DB.db.avant_suivi_simplifie_<date>

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


REPRISE_LOG = "Migration : reprise du suivi des réinjections"


def reprendre(con, source):
    """Ajoute au suivi simplifié les valeurs de l'ancienne version lues dans `source`
    (schéma de la base source : nom de la base attachée, ou "main").

    Ajout (et non remplacement) : si le bot a déjà suivi des réinjections avec la
    nouvelle version, elles sont conservées et combinées.
    Returns: (nombre de paliers repris, capital repris).
    """
    paliers = con.execute(f"""
        SELECT symbol, ID, COALESCE(reinj_benefice,0), COALESCE(reinj_capital,0), prix_moyen_capital, prix
        FROM {source}.ecart_bet WHERE COALESCE(reinj_benefice,0) > 0 OR COALESCE(reinj_capital,0) > 0""").fetchall()
    capital = {}
    for symbol, i, qb, qc, pmc, prix in paliers:
        p = pmc if (pmc and qc > 0) else prix
        q = qb + qc
        con.execute("""UPDATE main.ecart_bet SET
                         prix_moyen_reinj = (COALESCE(prix_moyen_reinj,0)*COALESCE(reinj_quantite,0) + ?*?)
                                            / (COALESCE(reinj_quantite,0) + ?),
                         reinj_quantite = COALESCE(reinj_quantite,0) + ?
                       WHERE symbol = ? AND ID = ?""", (q, p, q, q, symbol, i))
        capital[symbol] = capital.get(symbol, 0.0) + qc * p
    for symbol, en_attente in con.execute(
            f"SELECT symbol, COALESCE(up_TMP_capital,0) FROM {source}.Devises WHERE COALESCE(up_TMP_capital,0) > 0"):
        capital[symbol] = capital.get(symbol, 0.0) + en_attente
    for symbol, montant in capital.items():
        con.execute("UPDATE main.Devises SET capital_injecte = COALESCE(capital_injecte,0) + ? WHERE symbol = ?",
                    (montant, symbol))
    con.execute("INSERT INTO main.Log (date, emplacement, erreur, type, symbol) VALUES (?, ?, ?, ?, ?)",
                (str(datetime.now()), REPRISE_LOG,
                 f"{len(paliers)} paliers repris, capital injecté repris : "
                 + ", ".join(f"{s} {m:.2f}" for s, m in capital.items()), "DEBUG", None))
    return len(paliers), capital


def deja_repris(con):
    return con.execute("SELECT COUNT(*) FROM Log WHERE emplacement = ?", (REPRISE_LOG,)).fetchone()[0] > 0


def reprise_depuis_sauvegarde(fichier):
    """Cas où la migration a déjà été faite sans reprise : on reprend depuis la sauvegarde."""
    if not os.path.exists(fichier):
        sys.exit(f"Sauvegarde introuvable : {fichier}")
    if not bot_arrete():
        sys.exit("Le bot tourne (bot.lock verrouillé) : l'arrêter d'abord (bouton Éteindre ou krypto-bot.sh choix 6).")
    con = sqlite3.connect(DB, timeout=30)
    if any(c[1] not in colonnes(con, c[0]) for c in A_AJOUTER):
        sys.exit("La migration n'a pas encore été faite : lancer le script sans --reprendre.")
    if deja_repris(con):
        sys.exit("Les valeurs ont déjà été reprises (trace dans Log) : rien à faire.")
    con.execute("ATTACH DATABASE ? AS ancienne", (fichier,))
    if "reinj_capital" not in [r[1] for r in con.execute("PRAGMA ancienne.table_info(ecart_bet)")]:
        sys.exit("Cette sauvegarde ne contient pas l'ancien suivi (reinj_capital) : rien à reprendre.")
    avant = controle(con)
    sauvegarde = DB + ".avant_reprise_suivi_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    with sqlite3.connect(sauvegarde) as dest:
        con.backup(dest)
    print(f"Sauvegarde : {sauvegarde}")
    n, capital = reprendre(con, "ancienne")
    con.commit()
    if controle(con) != avant:
        sys.exit(f"ANOMALIE : grille ou stratégies modifiées. Restaurer la sauvegarde : cp {sauvegarde} {DB}")
    print(f"Reprise faite : {n} paliers, capital injecté " + (", ".join(f"{s} {m:.2f}" for s, m in capital.items()) or "aucun"))
    print("Contrôle OK : grille et stratégies inchangées.")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--reprendre":
        return reprise_depuis_sauvegarde(sys.argv[2])
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
    if "reinj_capital" in colonnes(con, "ecart_bet") and not deja_repris(con):
        n, capital = reprendre(con, "main")
        print(f"  Reprise : {n} paliers, capital injecté "
              + (", ".join(f"{s} {m:.2f}" for s, m in capital.items()) or "aucun"))
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
