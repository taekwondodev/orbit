"""Porta lo schema del database all'ultima versione. Ripetibile."""

from alembic import command
from alembic import config as alembic_config


def upgrade(engine):
    config = alembic_config.Config()
    config.set_main_option('script_location', 'orbit.db:migrations')
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
