"""Access to the orbs table."""

import sqlalchemy as sa

from orbit import orb as orb_model

metadata = sa.MetaData()

orbs = sa.Table(
    'orbs', metadata,
    sa.Column('id', sa.String(36), primary_key=True),
    sa.Column('project_id', sa.String(255), nullable=False, index=True),
    sa.Column('user_id', sa.String(255), nullable=False),
    sa.Column('vcpus', sa.Integer, nullable=False),
    sa.Column('memory_mb', sa.Integer, nullable=False),
    sa.Column('disk_gb', sa.Integer, nullable=False),
    sa.Column('image', sa.String(255), nullable=False),
    sa.Column('lease_id', sa.String(36), nullable=False),
    sa.Column('reservation_id', sa.String(36), nullable=False),
    sa.Column('stack_id', sa.String(36)),
    sa.Column('status', sa.String(16), nullable=False),
    sa.Column('fault', sa.Text),
    sa.Column('ssh_allowed_cidr', sa.String(18)),
    # One key per line: an OpenSSH key holds no line break.
    sa.Column('ssh_host_keys', sa.Text),
    sa.Column('created_at', sa.DateTime, nullable=False),
    sa.Column('updated_at', sa.DateTime),
    sa.Column('deleted_at', sa.DateTime),
)


class OrbRepository:

    def __init__(self, engine):
        self._engine = engine

    def add(self, orb):
        with self._engine.begin() as conn:
            conn.execute(orbs.insert().values(
                id=orb.id,
                project_id=orb.project_id,
                user_id=orb.user_id,
                vcpus=orb.size.vcpus,
                memory_mb=orb.size.memory_mb,
                disk_gb=orb.size.disk_gb,
                image=orb.image,
                lease_id=orb.lease_id,
                reservation_id=orb.reservation_id,
                stack_id=orb.stack_id,
                status=orb.status.value,
                fault=orb.fault,
                ssh_allowed_cidr=orb.ssh_allowed_cidr,
                created_at=orb.created_at,
            ))

    def get(self, project_id, orb_id):
        """The orb, or None if missing or in another project."""
        query = orbs.select().where(orbs.c.id == orb_id,
                                    orbs.c.project_id == project_id)
        with self._engine.connect() as conn:
            row = conn.execute(query).one_or_none()
        return _to_orb(row) if row else None

    def list(self, project_id, status=None):
        query = (orbs.select()
                 .where(orbs.c.project_id == project_id)
                 .order_by(orbs.c.created_at))
        if status is not None:
            query = query.where(orbs.c.status == status.value)
        with self._engine.connect() as conn:
            return [_to_orb(row) for row in conn.execute(query)]

    def update(self, orb_id, expected_status, **changes):
        """Apply the changes only if the status is still the expected one.

        The creation task and the reads write to the same row: whoever read
        an outdated status does not overwrite the more recent one. Host keys
        are written only if none are stored yet.
        Returns True if the row was updated.
        """
        values = {key: _column_value(key, value)
                  for key, value in changes.items()}
        values['updated_at'] = orb_model.utcnow()
        if changes.get('status') == orb_model.Status.DELETED:
            values['deleted_at'] = values['updated_at']
        query = (orbs.update()
                 .where(orbs.c.id == orb_id,
                        orbs.c.status == expected_status.value)
                 .values(**values))
        if 'ssh_host_keys' in changes:
            # Written once: a reader holding a stale row does not replace
            # them with a later console (docs/adr/0007).
            query = query.where(orbs.c.ssh_host_keys.is_(None))
        with self._engine.begin() as conn:
            return conn.execute(query).rowcount == 1


def _column_value(field, value):
    if field == 'status':
        return value.value
    if field == 'ssh_host_keys' and value is not None:
        return '\n'.join(value)
    return value


def _to_orb(row):
    return orb_model.Orb(
        id=row.id,
        project_id=row.project_id,
        user_id=row.user_id,
        size=orb_model.Size(row.vcpus, row.memory_mb, row.disk_gb),
        image=row.image,
        lease_id=row.lease_id,
        reservation_id=row.reservation_id,
        stack_id=row.stack_id,
        status=orb_model.Status(row.status),
        fault=row.fault,
        ssh_allowed_cidr=row.ssh_allowed_cidr,
        ssh_host_keys=(tuple(row.ssh_host_keys.split('\n'))
                       if row.ssh_host_keys is not None else None),
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )
