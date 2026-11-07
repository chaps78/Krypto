"""Verrou partagé entre le bot et l'API pour écrire dans DB.db sans conflit.

Principe (verrou de fichier flock, géré par le noyau) :
  - le bot tient le verrou pendant le traitement de chaque stratégie et le
    relâche entre deux stratégies (pendant sa pause) ;
  - l'API prend le verrou avant d'écrire : elle l'obtient donc à un moment où
    le bot n'a aucun traitement en cours, et tant qu'elle le tient le bot reste
    bloqué au début de la stratégie suivante (il est « en pause ») ;
  - dès que l'API relâche le verrou, le bot repart en relisant la base à jour.

Si le processus qui tient le verrou plante, le noyau le libère tout seul :
le bot ne peut pas rester en pause à cause d'un drapeau oublié.
"""
import fcntl
import os
import time
from contextlib import contextmanager

FICHIER = os.environ.get(
    "KRYPTO_VERROU_ECRITURE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.ecriture.lock"),
)


class VerrouOccupe(Exception):
    """Le verrou n'a pas pu être obtenu dans le délai demandé."""


@contextmanager
def tenir(attente=None, intervalle=0.2):
    """Tient le verrou pendant le bloc ``with``.

    attente : None = attendre aussi longtemps que nécessaire (le bot) ;
              sinon nombre maximal de secondes, puis VerrouOccupe (l'API).
    """
    f = open(FICHIER, "a")
    try:
        if attente is None:
            fcntl.flock(f, fcntl.LOCK_EX)
        else:
            limite = time.monotonic() + attente
            while True:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= limite:
                        raise VerrouOccupe(f"verrou d'écriture toujours pris après {attente} s")
                    time.sleep(intervalle)
        yield
    finally:
        f.close()  # fermer le fichier relâche le verrou


def est_pris():
    """Vrai si quelqu'un tient le verrou en ce moment (sans le garder)."""
    try:
        with tenir(attente=0):
            return False
    except VerrouOccupe:
        return True
