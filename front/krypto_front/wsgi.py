"""Point d'entrée WSGI utilisé par gunicorn."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "krypto_front.settings")
application = get_wsgi_application()
