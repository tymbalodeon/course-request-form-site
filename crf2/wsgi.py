"""
WSGI config for crf2 project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crf2.settings")
os.environ["LD_LIBRARY_PATH"] = "/usr/local/lib"

application = get_wsgi_application()
