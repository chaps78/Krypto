"""Client minimal de l'API du bot (lecture seule, via le tunnel SSH)."""
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class ApiError(Exception):
    """L'API du bot est injoignable ou a renvoyé une erreur."""


def get(path, **params):
    """Appelle GET {KRYPTO_API_URL}{path} et renvoie le JSON décodé.

    Les paramètres à None sont ignorés. Lève ApiError en cas de problème.
    """
    params = {k: v for k, v in params.items() if v not in (None, "")}
    url = settings.KRYPTO_API_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    if settings.KRYPTO_API_TOKEN:
        req.add_header("Authorization", f"Bearer {settings.KRYPTO_API_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise ApiError(f"L'API a répondu {e.code} sur {path}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ApiError(f"API injoignable ({settings.KRYPTO_API_URL}) : le tunnel SSH est-il actif ?") from e
