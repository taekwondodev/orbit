import flask
from keystonemiddleware import auth_token
from oslo_db.sqlalchemy import enginefacade

from orbit import clients, conf, creation, service
from orbit.api import v1
from orbit.conf import CONF
from orbit.db import api as db_api


def create_app(orbs):
    app = flask.Flask('orbit')
    app.extensions['orbit'] = orbs
    app.register_blueprint(v1.blueprint, url_prefix='/v1')
    return app


def create_wsgi_app():
    conf.check_api_options()
    engine = enginefacade.writer.get_engine()
    # The only schema. create_all creates the table where missing and never
    # alters an existing one: a change to the table needs a new database.
    db_api.metadata.create_all(engine)
    repository = db_api.OrbRepository(engine)
    creator = creation.Creator(repository, creation.load_template())
    orbs = service.Orbs(repository, clients.for_auth, creator)
    return auth_token.AuthProtocol(
        create_app(orbs).wsgi_app, {'oslo_config_config': CONF}
    )
