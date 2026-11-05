"""Client minimal de l'API du bot (lecture seule, via le tunnel SSH)."""
import http.client
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
        try:
            detail = json.load(e).get("detail")
        except (ValueError, AttributeError):
            detail = None
        raise ApiError(f"L'API a répondu {e.code} sur {path}" + (f" : {detail}" if isinstance(detail, str) else "")) from e
    except TimeoutError as e:
        raise ApiError(f"L'API n'a pas répondu en 10 s sur {path} : réessayez dans un instant") from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            raise ApiError(f"L'API n'a pas répondu en 10 s sur {path} : réessayez dans un instant") from e
        raise ApiError(f"API injoignable ({settings.KRYPTO_API_URL}) : le tunnel SSH est-il actif ?") from e
    except (http.client.HTTPException, ValueError) as e:
        raise ApiError(f"Réponse incomplète ou illisible de l'API sur {path}") from e
    except OSError as e:
        raise ApiError(f"API injoignable ({settings.KRYPTO_API_URL}) : le tunnel SSH est-il actif ?") from e
