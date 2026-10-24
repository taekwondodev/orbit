"""The WSGI application of orbit-api: Flask behind keystonemiddleware."""

import flask
from keystonemiddleware import auth_token
from oslo_db.sqlalchemy import enginefacade

from orbit.api import v1
from orbit import clients
from orbit import conf
from orbit.conf import CONF
from orbit import creation
from orbit.db import api as db_api
from orbit import service


def create_app(orbs):
    """The application without authentication, for the tests."""
    app = flask.Flask('orbit')
    app.config['ORBS'] = orbs
    app.register_blueprint(v1.blueprint, url_prefix='/v1')
    return app


def create_wsgi_app():
    """The served application: every request goes through Keystone."""
    conf.check_api_options()
    repository = db_api.OrbRepository(enginefacade.writer.get_engine())
    creator = creation.Creator(repository, creation.load_template())
    orbs = service.Orbs(repository, clients.for_auth, creator)
    return auth_token.AuthProtocol(create_app(orbs).wsgi_app,
                                   {'oslo_config_config': CONF})
