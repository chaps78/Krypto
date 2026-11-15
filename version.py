"""Numéro de version de Krypto (fichier VERSION à la racine) et commit git du dépôt.

Le même dépôt sert au bot, à l'API et au front : chaque serveur affiche ainsi la
version du code qu'il fait tourner. Numérotation : <étape>.<livraison>,
incrémentée à chaque version poussée.
"""
import os
import subprocess

RACINE = os.path.dirname(os.path.abspath(__file__))


def version():
    """Contenu du fichier VERSION, ou "?" s'il est illisible."""
    try:
        with open(os.path.join(RACINE, "VERSION")) as f:
            return f.read().strip() or "?"
    except OSError:
        return "?"


def commit():
    """Commit git court du dépôt (ex. "de8726d"), ou None."""
    try:
        r = subprocess.run(["git", "-C", RACINE, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None
