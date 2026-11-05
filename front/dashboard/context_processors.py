"""Données communes à toutes les pages (menu)."""
from . import api_client


def etat_bot(request):
    """Etat du bot pour la pastille du menu : "marche", "fige", "arrete" ou "inconnu".

    - marche  : battement récent (pastille verte)
    - fige    : service systemd actif mais plus de battement (pastille rouge)
    - arrete  : pas de battement récent (pastille rouge)
    - inconnu : API injoignable, donc état impossible à connaître (pastille grise)
    """
    if not request.user.is_authenticated:
        return {}
    try:
        bot = api_client.get("/bot")
    except Exception:  # la pastille ne doit jamais faire tomber une page
        return {"bot_etat": "inconnu", "bot_info": "API injoignable : état du bot inconnu"}
    age = bot.get("age_secondes")
    if bot.get("en_marche"):
        etat, info = "marche", f"Bot en marche (battement il y a {age} s)"
    elif bot.get("service") == "active":
        etat, info = "fige", f"Bot figé : service actif mais aucun battement depuis {age} s"
    else:
        etat = "arrete"
        info = "Bot arrêté" + (f" (dernier battement il y a {age} s)" if age is not None else "")
    return {"bot_etat": etat, "bot_info": info}
