"""Brings the database schema to the latest version. Repeatable."""

from alembic import command
from alembic import config as alembic_config


def upgrade(engine):
    config = alembic_config.Config()
    config.set_main_option('script_location', 'orbit.db:migrations')
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
