"""L'applicazione WSGI di orbit-api: Flask dietro keystonemiddleware."""

import flask
from keystonemiddleware import auth_token

from orbit.api import v1
from orbit.conf import CONF


def create_app():
    """L'applicazione senza autenticazione, per i test."""
    app = flask.Flask('orbit')
    app.register_blueprint(v1.blueprint, url_prefix='/v1')
    return app


def create_wsgi_app():
    """L'applicazione servita: ogni richiesta passa da Keystone."""
    return auth_token.AuthProtocol(
        create_app().wsgi_app, {'oslo_config_config': CONF})
