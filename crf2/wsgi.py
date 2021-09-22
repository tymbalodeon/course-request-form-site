import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crf2.settings")
os.environ["LD_LIBRARY_PATH"] = "/usr/local/lib"

application = get_wsgi_application()
