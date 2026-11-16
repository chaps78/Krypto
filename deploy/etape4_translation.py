"""Étape 4 : déplacement du pic (translation), consignes 1 et 2. Migration unique, 2026-11.

Ajoute, sans rien modifier d'existant (bets, ordres, réinjection inchangés) :
  ecart_bet : eloigne_depuis (chronomètre : date à laquelle le palier est passé à
              6 paliers ou plus du palier courant), source_depuis (date à
              laquelle il est devenu source éligible) ;
  Devises   : tr_distance (6 paliers), tr_duree (48 h), tr_gain_min (4,5) ;
  table journal_ruptures : une ligne quand un palier devient source éligible,
              une ligne quand il cesse de l'être.
  Consigne 2 : Devises.translation ('off' par défaut : aucun effet), tr_plancher (3),
              tr_ordre_mini (6), tr_notif_observation (0),
              compteurs tr_cout_paye / tr_cout_reconnu ; journal_reinjection : colonnes tr_*.
Déjà passée pour la consigne 1 : la relancer ajoute seulement les colonnes de la consigne 2.
Puis reconstitue les chronomètres des stratégies actives à partir de
l'historique des ordres limites exécutés (sinon aucune source avant 48 h).
Prérequis : migration de l'étape 3 (deploy/etape3_equilibrage.py).

A lancer sur le serveur du bot, BOT ARRÊTÉ, AVANT de redémarrer le bot avec le
nouveau code :
    python3 deploy/etape4_translation.py

- refuse de tourner si le bot tourne (verrou bot.lock pris) ;
- sauvegarde d'abord la base dans DB.db.avant_etape4_<date> ;
- relançable sans risque (ne fait que ce qui reste à faire ; les chronomètres
  ne sont reconstitués que lors de l'ajout des colonnes) ;
- vérifie que la grille et les stratégies sont inchangées.
"""
import fcntl
import os
import sqlite3
import sys
from datetime import datetime

BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BOT_DIR)
import translation  # noqa: E402

DB = os.path.join(BOT_DIR, "DB.db")
LOCK = os.path.join(BOT_DIR, "bot.lock")

A_AJOUTER = [
    ("ecart_bet", "eloigne_depuis", "TEXT"),
    ("ecart_bet", "source_depuis", "TEXT"),
    ("Devises", "tr_distance", "INTEGER DEFAULT 6"),
    ("Devises", "tr_duree", "REAL DEFAULT 48"),
    ("Devises", "tr_gain_min", "REAL DEFAULT 4.5"),
    # Consigne 2 : translation
    ("Devises", "translation", "TEXT DEFAULT 'off'"),
    ("Devises", "tr_plancher", "REAL DEFAULT 3"),
    ("Devises", "tr_ordre_mini", "REAL DEFAULT 6"),
    ("Devises", "tr_notif_observation", "INTEGER DEFAULT 0"),
    ("Devises", "tr_cout_paye", "REAL DEFAULT 0"),
    ("Devises", "tr_cout_reconnu", "REAL DEFAULT 0"),
    ("journal_reinjection", "tr_mode", "TEXT"),
    ("journal_reinjection", "tr_applique", "INTEGER"),
    ("journal_reinjection", "tr_raison", "TEXT"),
    ("journal_reinjection", "tr_cas", "TEXT"),
    ("journal_reinjection", "tr_source", "INTEGER"),
    ("journal_reinjection", "tr_distance", "INTEGER"),
    ("journal_reinjection", "tr_position", "TEXT"),
    ("journal_reinjection", "tr_gain_source_avant", "REAL"),
    ("journal_reinjection", "tr_gain_source_apres", "REAL"),
    ("journal_reinjection", "tr_recepteurs", "TEXT"),
    ("journal_reinjection", "tr_q", "REAL"),
    ("journal_reinjection", "tr_cout", "REAL"),
    ("journal_reinjection", "tr_nature", "TEXT"),
    ("journal_reinjection", "tr_vertical", "REAL"),
    ("journal_reinjection", "tr_ordre", "TEXT"),
    ("journal_reinjection", "tr_prix_exec", "REAL"),
    ("journal_reinjection", "tr_cout_reel", "REAL"),
]
TABLES = {
    "journal_ruptures": """CREATE TABLE journal_ruptures (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        date            TEXT NOT NULL,   -- ISO UTC
        symbol          TEXT NOT NULL,
        palier          INTEGER,
        evenement       TEXT,            -- eligible / fin
        raison          TEXT,            -- source éligible, retour du prix, gain ≤ 4,5
        gain            REAL,            -- gain(S) = bet × g(S), en cotation
        distance        INTEGER,         -- D(S) = |S − palier courant|
        palier_courant  INTEGER,
        prix_courant    REAL,            -- prix du palier courant
        prix_palier     REAL,
        eloigne_depuis  TEXT,            -- chronomètre au moment de l'événement
        source_depuis   TEXT             -- pour une fin : depuis quand il était éligible
    )""",
}


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


def date_ordre(fin, debut):
    """Date d'exécution d'un ordre (date_fin, sinon date_debut), ou None."""
    for texte in (fin, debut):
        try:
            return datetime.fromisoformat(texte)
        except (TypeError, ValueError):
            continue
    return None


def reconstituer(con):
    """Chronomètres des stratégies actives, rejoués sur les ordres limites exécutés."""
    for (symbol,) in con.execute("SELECT symbol FROM Devises WHERE actif = 1").fetchall():
        ids = [r[0] for r in con.execute("SELECT ID FROM ecart_bet WHERE symbol = ?", (symbol,))]
        execs = []
        for fin, debut, palier in con.execute("SELECT date_fin, date_debut, ID_ecart FROM Ordres WHERE symbol = ? "
                                              "AND status = 'FILLED' AND type = 'LIMIT' AND ID_ecart IS NOT NULL",
                                              (symbol,)):
            d = date_ordre(fin, debut)
            if d is not None:
                execs.append((d, palier))
        if not ids or not execs:
            print(f"  {symbol} : pas d'historique, chronomètres démarrés par le bot")
            continue
        chronos = translation.reconstituer_chronos(execs, ids, translation.DEFAUTS["distance"])
        con.executemany("UPDATE ecart_bet SET eloigne_depuis = ? WHERE symbol = ? AND ID = ?",
                        [(d.isoformat() if d else None, symbol, i) for i, d in chronos.items()])
        actifs = [d for d in chronos.values() if d]
        print(f"  {symbol} : {len(actifs)} paliers éloignés sur {len(ids)}"
              + (f", le plus ancien depuis {min(actifs):%d/%m/%Y %H:%M}" if actifs else ""))


def main():
    if not os.path.exists(DB):
        sys.exit(f"Base introuvable : {DB}")
    if not bot_arrete():
        sys.exit("Le bot tourne (bot.lock verrouillé) : l'arrêter d'abord (bouton Éteindre ou krypto-bot.sh choix 6).")
    con = sqlite3.connect(DB, timeout=30)
    if "eq_seuil" not in colonnes(con, "Devises"):
        sys.exit("Étape 3 absente : lancer d'abord deploy/etape3_equilibrage.py")
    ajouts = [c for c in A_AJOUTER if c[1] not in colonnes(con, c[0])]
    tables = [t for t in TABLES if not colonnes(con, t)]
    if not ajouts and not tables:
        print("L'étape 4 (consignes 1 et 2) est déjà en place : rien à faire.")
        return
    avant = controle(con)
    sauvegarde = DB + ".avant_etape4_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    with sqlite3.connect(sauvegarde) as dest:
        con.backup(dest)
    print(f"Sauvegarde : {sauvegarde}")
    chronos_a_faire = any(c[1] == "eloigne_depuis" for c in ajouts)
    for table, colonne, definition in ajouts:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
        print(f"  + {table}.{colonne}")
    for t in tables:
        con.execute(TABLES[t])
        print(f"  + table {t}")
    if chronos_a_faire:
        print("Chronomètres reconstitués :")
        reconstituer(con)
    con.commit()
    apres = controle(con)
    manquantes = [c[1] for c in A_AJOUTER if c[1] not in colonnes(con, c[0])] + [t for t in TABLES if not colonnes(con, t)]
    if manquantes or apres != avant:
        sys.exit(f"ANOMALIE : manquants {manquantes}, contrôle avant {avant}, après {apres}. "
                 f"Restaurer la sauvegarde : cp {sauvegarde} {DB}")
    print(f"Étape 4 en place (déplacement du pic : off partout). Contrôle OK : "
          f"{apres[0][0]} paliers et {apres[1][0]} stratégies inchangés.")
    con.close()


if __name__ == "__main__":
    main()
