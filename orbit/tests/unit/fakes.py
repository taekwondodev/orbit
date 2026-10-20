"""Oggetti di prova condivisi dai test unitari."""

import sqlalchemy as sa

from orbit.db import api as db_api
from orbit.db import migration
from orbit import orb as orb_model


def database():
    """Un database SQLite in memoria con lo schema delle migrazioni."""
    engine = sa.create_engine('sqlite://',
                              poolclass=sa.pool.StaticPool,
                              connect_args={'check_same_thread': False})
    migration.upgrade(engine)
    return engine


def orb(**overrides):
    values = dict(
        id='11111111-1111-1111-1111-111111111111',
        project_id='project-a',
        user_id='user-a',
        size=orb_model.Size(vcpus=2, memory_mb=4096, disk_gb=20),
        image='cirros',
        lease_id='lease-1',
        reservation_id='reservation-1',
        status=orb_model.Status.RESERVING,
        created_at=orb_model.utcnow(),
    )
    values.update(overrides)
    return orb_model.Orb(**values)


def repository():
    return db_api.OrbRepository(database())
