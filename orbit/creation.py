"""The creation task: waits for the active reservation and creates the stack.

Runs in a thread of the process that received the request, with that
request's token, and does not survive a restart: an orb left without a stack
beyond creation_timeout counts as interrupted on the next read
(docs/design/state.md, Reconciliation).
"""

import datetime
import importlib.resources
import threading
import time

from oslo_log import log

from orbit import clients as orbit_clients
from orbit.conf import CONF
from orbit import orb as orb_model

LOG = log.getLogger(__name__)
Status = orb_model.Status

STACK_TAG = 'orbit'


def load_template():
    return (importlib.resources.files('orbit') / 'templates' / 'orb.yaml'
            ).read_text()


class Creator:

    def __init__(self, repository, template, sleep=time.sleep,
                 clock=orb_model.utcnow):
        self._repository = repository
        self._template = template
        self._sleep = sleep
        self._clock = clock

    def start(self, orb, clients, public_key):
        threading.Thread(target=self.run, args=(orb, clients, public_key),
                         name=f'create-{orb.resource_name}',
                         daemon=True).start()

    def run(self, orb, clients, public_key):
        try:
            self._create(orb, clients, public_key)
        except Exception:
            LOG.exception('Creation of %s interrupted', orb.resource_name)
            self._fail(orb, 'creation interrupted by an internal error')

    def _fail(self, orb, fault):
        self._repository.update(orb.id, Status.RESERVING,
                                status=Status.ERROR, fault=fault)

    def _create(self, orb, clients, public_key):
        try:
            active = self._wait_for_reservation(orb, clients.blazar)
        except orbit_clients.Rejected as e:
            LOG.warning('Blazar rejects the read of %s: %s',
                        orb.resource_name, e)
            self._fail(orb, f'reservation not readable: {e}')
            return
        if not active:
            LOG.warning('Reservation of %s not active: no stack',
                        orb.resource_name)
            return
        current = self._repository.get(orb.project_id, orb.id)
        if current.status is not Status.RESERVING:
            return
        try:
            stack_id = clients.heat.create_stack(
                orb.resource_name, self._template,
                self._parameters(orb, public_key), STACK_TAG)
        except (orbit_clients.Rejected, orbit_clients.Unavailable) as e:
            self._fail(orb, str(e))
            return
        if not self._repository.update(orb.id, Status.RESERVING,
                                       status=Status.BUILDING,
                                       stack_id=stack_id):
            # The orb changed while the stack was being created: it was
            # deleted, or declared interrupted. The stack no longer belongs
            # to it.
            clients.heat.delete_stack(orb.resource_name)

    def _wait_for_reservation(self, orb, blazar):
        deadline = orb.created_at + datetime.timedelta(
            seconds=CONF.orbs.creation_timeout)
        while self._clock() < deadline:
            try:
                lease = blazar.get_lease(orb.lease_id)
            except orbit_clients.Unavailable:
                LOG.warning('Blazar does not respond, retrying for %s',
                            orb.resource_name)
            else:
                if lease is None or lease.is_failed:
                    return False
                if lease.is_active:
                    return True
            self._sleep(CONF.orbs.reservation_poll_interval)
        return False

    @staticmethod
    def _parameters(orb, public_key):
        return {
            'orb_id': orb.id,
            'reservation_id': orb.reservation_id,
            'image': orb.image,
            'public_key': public_key,
            'public_network': CONF.orbs.public_network,
            'ssh_allowed_cidr': orb.ssh_allowed_cidr,
        }
