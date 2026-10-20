"""L'applicazione WSGI di orbit-api: Flask dietro keystonemiddleware."""

import flask
from keystonemiddleware import auth_token
from oslo_db.sqlalchemy import enginefacade

from orbit.api import v1
from orbit import clients
from orbit.conf import CONF
from orbit.db import api as db_api
from orbit import service


def create_app(orbs):
    """L'applicazione senza autenticazione, per i test."""
    app = flask.Flask('orbit')
    app.config['ORBS'] = orbs
    app.register_blueprint(v1.blueprint, url_prefix='/v1')
    return app


def create_wsgi_app():
    """L'applicazione servita: ogni richiesta passa da Keystone."""
    repository = db_api.OrbRepository(enginefacade.writer.get_engine())
    orbs = service.Orbs(repository, clients.for_auth)
    return auth_token.AuthProtocol(create_app(orbs).wsgi_app,
                                   {'oslo_config_config': CONF})
