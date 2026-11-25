"""WSGI config for Easy 66 & Co project."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'easy66.settings')
application = get_wsgi_application()
app = application
