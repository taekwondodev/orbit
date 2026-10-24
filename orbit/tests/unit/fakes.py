"""Test doubles shared by the unit tests."""

import dataclasses

import sqlalchemy as sa

from orbit import clients
from orbit.db import api as db_api
from orbit.db import migration
from orbit import orb as orb_model


def database():
    """An in-memory SQLite database with the migrations' schema."""
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
        ssh_allowed_cidr='198.51.100.20/32',
    )
    values.update(overrides)
    return orb_model.Orb(**values)


def repository():
    return db_api.OrbRepository(database())


PUBLIC_KEY = ('ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGOhftmAAN4BAVfQqYzlzcso'
              '+BQ5/8gHIjywO8hhD6es test@orbit')


class FakeBlazar:
    """An in-memory Blazar: leases are born waiting for activation."""

    def __init__(self):
        self.leases = {}
        self.created = []
        self.refuse_with = None

    def create_lease(self, name, size, end_date):
        if self.refuse_with:
            raise self.refuse_with
        self.created.append((name, size, end_date))
        number = len(self.created)
        lease = clients.Lease(id=f'lease-{number}',
                              status='PENDING',
                              reservation_id=f'reservation-{number}',
                              reservation_status='pending')
        self.leases[lease.id] = lease
        return lease

    def get_lease(self, lease_id):
        return self.leases.get(lease_id)

    def delete_lease(self, lease_id):
        self.leases.pop(lease_id, None)

    def activate(self, lease_id):
        lease = self.leases[lease_id]
        self.leases[lease_id] = dataclasses.replace(
            lease, status='ACTIVE', reservation_status='active')


class FakeHeat:
    """An in-memory Heat: stacks are born under construction."""

    def __init__(self):
        self.stacks = {}
        self.created = []
        self.refuse_with = None

    def create_stack(self, name, template, parameters, tag):
        if self.refuse_with:
            raise self.refuse_with
        self.created.append((name, template, parameters, tag))
        stack = clients.Stack(id=f'stack-{len(self.created)}',
                              status='CREATE_IN_PROGRESS', status_reason='',
                              outputs={})
        self.stacks[name] = stack
        return stack.id

    def get_stack(self, name):
        return self.stacks.get(name)

    def delete_stack(self, name):
        self.stacks.pop(name, None)

    def set_status(self, name, status, reason='', **outputs):
        self.stacks[name] = dataclasses.replace(
            self.stacks[name], status=status, status_reason=reason,
            outputs=outputs)


class FakeCreator:
    """Records the started creations without running them."""

    def __init__(self):
        self.started = []

    def start(self, orb, clients, public_key):
        self.started.append((orb, public_key))


HOST_KEY_ED25519 = ('ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMAjisZdvWGFparxBlql'
                    'B/fzA2Q+G0SQNgba9SaQRxJT')
HOST_KEY_ECDSA = ('ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAI'
                  'bmlzdHAyNTYAAABBBJ8l4ljo43v0fplqGt9j7zEwq4HpAi8GwTzO6U4m'
                  'vM2TcZ9FCbJ44kddcn0w9m48yfEIWRTyFfeoKTd9nnHzEpM=')

# The tail of an Ubuntu console as cloud-init leaves it, line endings
# included.
CONSOLE = (
    '[   10.112233] cloud-init[812]: Cloud-init v. 24.1 finished\r\n'
    '-----BEGIN SSH HOST KEY KEYS-----\r\n'
    f'{HOST_KEY_ECDSA} root@orb\r\n'
    f'{HOST_KEY_ED25519} root@orb\r\n'
    '-----END SSH HOST KEY KEYS-----\r\n'
    'Ubuntu 24.04 LTS orb ttyS0\r\n')


class FakeNova:

    def __init__(self):
        self.servers = {}
        self.consoles = {}
        self.console_reads = 0
        self.console_refused_with = None

    def get_server(self, server_id):
        return self.servers.get(server_id)

    def get_console_output(self, server_id):
        self.console_reads += 1
        if self.console_refused_with:
            raise self.console_refused_with
        return self.consoles.get(server_id, '')


def fake_clients():
    return clients.Clients(blazar=FakeBlazar(), heat=FakeHeat(),
                           nova=FakeNova())
