"""Configuration du front Krypto.

Les valeurs sensibles ou propres au serveur viennent de variables
d'environnement (fichier .env chargé par systemd, voir deploy/) :
    DJANGO_SECRET_KEY   obligatoire en production
    DJANGO_DEBUG        "1" pour le mode debug (développement uniquement)
    DJANGO_ALLOWED_HOSTS  liste séparée par des virgules (ex. "100.90.255.68,mermoz")
    KRYPTO_API_URL      URL de l'API du bot (défaut : tunnel SSH local)
    KRYPTO_API_TOKEN    token de l'API, si activé côté bot
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Charge front/.env s'il existe (lignes CLE=valeur), sans écraser l'environnement.
_env = BASE_DIR / ".env"
if _env.exists():
    for _ligne in _env.read_text().splitlines():
        _ligne = _ligne.strip()
        if _ligne and not _ligne.startswith("#") and "=" in _ligne:
            _cle, _val = _ligne.split("=", 1)
            os.environ.setdefault(_cle.strip(), _val.strip())

DEBUG = os.environ.get("DJANGO_DEBUG") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or ("dev-only-insecure-key" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY doit être défini (voir deploy/krypto-front.env.example)")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]

KRYPTO_API_URL = os.environ.get("KRYPTO_API_URL", "http://127.0.0.1:8000").rstrip("/")
KRYPTO_API_TOKEN = os.environ.get("KRYPTO_API_TOKEN")
# Stratégies dont la page Grille peut afficher le tableau ecart_bet (séparées par des virgules)
KRYPTO_GRILLE_SYMBOLS = [s.strip() for s in os.environ.get("KRYPTO_GRILLE_SYMBOLS", "PEPEEUR_N91").split(",") if s.strip()]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "krypto_front.urls"
WSGI_APPLICATION = "krypto_front.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "dashboard.context_processors.etat_bot",
            ],
        },
    },
]

# Base propre au front : uniquement les utilisateurs et sessions.
# Les données du bot passent exclusivement par l'API.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "kpi"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_AGE = 7 * 24 * 3600

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
