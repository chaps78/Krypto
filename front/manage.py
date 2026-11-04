#!/usr/bin/env python
"""Point d'entrée Django (migrate, createsuperuser, runserver...)."""
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "krypto_front.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
