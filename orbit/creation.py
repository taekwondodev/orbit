"""Il compito di creazione: attende la prenotazione attiva e crea lo stack.

Gira in un thread del processo che ha ricevuto la richiesta, col token di
quella richiesta, e non sopravvive a un riavvio: un orb rimasto senza stack
oltre creation_timeout risulta interrotto alla lettura successiva
(docs/design/stato.md, Riallineamento).
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
        except orbit_clients.Rejected as e:
            self._fail(orb, f'prenotazione non leggibile: {e}')
        except Exception:
            LOG.exception('Creazione di %s interrotta', orb.resource_name)
            self._fail(orb, 'creazione interrotta da un errore interno')

    def _fail(self, orb, fault):
        self._repository.update(orb.id, Status.RESERVING,
                                status=Status.ERROR, fault=fault)

    def _create(self, orb, clients, public_key):
        if not self._wait_for_reservation(orb, clients.blazar):
            LOG.warning('Prenotazione di %s non attiva: nessuno stack',
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
            # L'orb e cambiato mentre lo stack nasceva: e stato cancellato,
            # o dichiarato interrotto. Lo stack non gli appartiene piu.
            clients.heat.delete_stack(orb.resource_name)

    def _wait_for_reservation(self, orb, blazar):
        deadline = orb.created_at + datetime.timedelta(
            seconds=CONF.orbs.creation_timeout)
        while self._clock() < deadline:
            try:
                lease = blazar.get_lease(orb.lease_id)
            except orbit_clients.Unavailable:
                LOG.warning('Blazar non risponde, ritento per %s',
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
            'network': CONF.orbs.network,
            'public_network': CONF.orbs.public_network,
            'ssh_allowed_cidr': CONF.orbs.ssh_allowed_cidr,
        }
