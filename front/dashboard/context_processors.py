"""Données communes à toutes les pages (menu)."""
from django.conf import settings

from . import api_client


def etat_bot(request):
    """Etat du bot pour la pastille du menu : "marche", "fige", "arrete" ou "inconnu".

    - marche  : battement récent (pastille verte)
    - fige    : service systemd actif mais plus de battement (pastille rouge)
    - arrete  : pas de battement récent (pastille rouge)
    - inconnu : API injoignable, donc état impossible à connaître (pastille grise)
    - arret_en_cours / demarrage : arrêt ou démarrage du service en cours

    bot_action : bouton proposé dans le menu, "arreter", "demarrer" ou None
    (aucun bouton pour un bot lancé à la main, hors service systemd).
    version_front / commit_front, version_api / commit_api : versions affichées à côté du logo
    (une version d'API différente de celle du front est signalée en rouge).
    """
    if not request.user.is_authenticated:
        return {}
    version = {"version_front": settings.KRYPTO_VERSION, "commit_front": settings.KRYPTO_COMMIT}
    try:
        bot = api_client.get("/bot")
    except Exception:  # la pastille ne doit jamais faire tomber une page
        return {"bot_etat": "inconnu", "bot_info": "API injoignable : état du bot inconnu", "bot_action": None, **version}
    version.update(version_api=bot.get("version"), commit_api=bot.get("commit"))
    age = bot.get("age_secondes")
    service = bot.get("service")
    action = None
    if service == "deactivating":
        etat, info = "arret_en_cours", "Arrêt en cours : le bot termine la stratégie en cours (jusqu'à 2 min)"
    elif service == "activating":
        etat, info = "demarrage", "Démarrage du bot en cours"
    elif bot.get("en_marche"):
        etat, info = "marche", f"Bot en marche (battement il y a {age} s)"
        if service == "active":
            action = "arreter"
        else:
            info += " : lancé à la main, à arrêter depuis le serveur"
    elif service == "active":
        etat, info, action = "fige", f"Bot figé : service actif mais aucun battement depuis {age} s", "arreter"
    else:
        etat = "arrete"
        info = "Bot arrêté" + (f" (dernier battement il y a {age} s)" if age is not None else "")
        action = "demarrer" if service is not None else None
    return {"bot_etat": etat, "bot_info": info, "bot_action": action, **version}
