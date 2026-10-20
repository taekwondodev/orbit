"""orbit-dbsync: crea o aggiorna lo schema del database. Ripetibile."""

import sys

from oslo_db.sqlalchemy import enginefacade

from orbit import conf
from orbit.db import migration


def main():
    conf.parse_args(sys.argv[1:])
    migration.upgrade(enginefacade.writer.get_engine())
