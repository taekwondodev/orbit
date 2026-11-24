"""Entry point for uwsgi: ``module = orbit.api.wsgi:application``."""

from orbit import conf
from orbit.api import app

conf.parse_args([])
application = app.create_wsgi_app()
