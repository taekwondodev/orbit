"""Punto d'ingresso per uwsgi: ``module = orbit.api.wsgi:application``."""

from orbit.api import app
from orbit import conf

conf.parse_args([])
application = app.create_wsgi_app()
