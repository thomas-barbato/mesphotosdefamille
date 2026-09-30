"""Copy into the WSGI file linked from PythonAnywhere's Web tab."""
import os
import sys

project_path = "/home/mesphotosdefamille/mesphotosdefamille"
if project_path not in sys.path:
    sys.path.insert(0, project_path)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_DEBUG", "0")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
