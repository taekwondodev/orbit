"""Chiamate a Blazar, Heat e Nova col token di chi ha fatto la richiesta.

Ogni client traduce le risposte nei pochi fatti che servono al servizio e
nelle eccezioni di questo modulo; il resto del codice non vede HTTP.
"""

import dataclasses

from keystoneauth1 import adapter
from keystoneauth1 import exceptions as ks_exc
from keystoneauth1 import session as ks_session


class Unavailable(Exception):
    """Il servizio chiamato non risponde o risponde con un errore suo."""


class CapacityExhausted(Exception):
    """Blazar non ha un host con posto per la taglia chiesta."""


class Rejected(Exception):
    """Il servizio chiamato ha rifiutato la richiesta, col suo motivo."""


@dataclasses.dataclass(frozen=True)
class Clients:
    blazar: 'Blazar'
    heat: 'Heat'
    nova: 'Nova'


def for_auth(auth):
    """I client che agiscono a nome di chi possiede ``auth``."""
    session = ks_session.Session(auth=auth)
    return Clients(blazar=Blazar(session), heat=Heat(session),
                   nova=Nova(session))


class _Client:
    service_type = None

    def __init__(self, session):
        self._api = adapter.Adapter(session, service_type=self.service_type,
                                    interface='public')

    def _call(self, method, url, **kwargs):
        try:
            return self._api.request(url, method, **kwargs)
        except (ks_exc.ConnectionError, ks_exc.EndpointNotFound) as e:
            raise Unavailable(f'{self.service_type}: {e}') from e
        except ks_exc.HttpServerError as e:
            raise Unavailable(f'{self.service_type}: {_error_text(e)}') from e

    def _get_or_none(self, url):
        try:
            return self._call('GET', url).json()
        except ks_exc.NotFound:
            return None

    def _delete_if_present(self, url):
        try:
            self._call('DELETE', url)
        except ks_exc.NotFound:
            pass


def _error_text(error):
    return error.response.text if error.response is not None else str(error)


@dataclasses.dataclass(frozen=True)
class Lease:
    id: str
    status: str
    reservation_id: str
    reservation_status: str

    @property
    def is_active(self):
        return self.reservation_status == 'active'

    @property
    def is_failed(self):
        return self.status == 'ERROR' or self.reservation_status == 'error'


class Blazar(_Client):
    service_type = 'reservation'

    # Blazar segnala la capacita esaurita con l'eccezione
    # NotEnoughHostsAvailable, che non dichiara un codice: arriva come 500 e
    # si riconosce solo dal messaggio. Fonti: blazar/manager/exceptions.py e
    # blazar/api/v1/utils.py.
    _CAPACITY_MESSAGE = 'Not enough hosts available'

    def create_lease(self, name, size, end_date):
        body = {
            'name': name,
            'start_date': 'now',
            'end_date': end_date,
            'reservations': [{
                'resource_type': 'virtual:instance',
                'vcpus': size.vcpus,
                'memory_mb': size.memory_mb,
                'disk_gb': size.disk_gb,
                'amount': 1,
                'affinity': None,
                'resource_properties': '',
            }],
            'events': [],
        }
        try:
            response = self._call('POST', '/leases', json=body)
        except Unavailable as e:
            if self._CAPACITY_MESSAGE in str(e):
                raise CapacityExhausted(self._CAPACITY_MESSAGE) from e
            raise
        return _lease(response.json()['lease'])

    def get_lease(self, lease_id):
        """Il lease, o None se non esiste piu."""
        body = self._get_or_none(f'/leases/{lease_id}')
        return _lease(body['lease']) if body else None

    def delete_lease(self, lease_id):
        """Cancella il lease; un lease gia sparito non e un errore."""
        self._delete_if_present(f'/leases/{lease_id}')


def _lease(body):
    reservation = body['reservations'][0]
    return Lease(id=body['id'], status=body['status'],
                 reservation_id=reservation['id'],
                 reservation_status=reservation['status'])


@dataclasses.dataclass(frozen=True)
class Stack:
    id: str
    status: str
    status_reason: str
    outputs: dict


class Heat(_Client):
    service_type = 'orchestration'

    def create_stack(self, name, template, parameters, tag):
        """Crea lo stack e ne restituisce l'identificativo.

        Heat costruisce in modo asincrono: la risposta arriva appena lo stack
        e accettato, e lo stato si scopre leggendolo.
        """
        body = {
            'stack_name': name,
            'template': template,
            'parameters': parameters,
            'tags': tag,
            # Uno stack fallito resta in piedi per la diagnosi: lo cancella
            # solo DELETE sull'orb (docs/design/api.md).
            'disable_rollback': True,
        }
        try:
            response = self._call('POST', '/stacks', json=body)
        except ks_exc.HTTPClientError as e:
            raise Rejected(_heat_message(e)) from e
        return response.json()['stack']['id']

    def get_stack(self, name):
        """Lo stack col nome dato, o None se non esiste o e gia cancellato.

        Heat risponde a /stacks/{nome} con un rinvio a /stacks/{nome}/{id},
        che keystoneauth segue.
        """
        body = self._get_or_none(f'/stacks/{name}')
        if body is None or body['stack']['stack_status'] == 'DELETE_COMPLETE':
            return None
        stack = body['stack']
        outputs = {output['output_key']: output.get('output_value')
                   for output in stack.get('outputs') or []}
        return Stack(id=stack['id'], status=stack['stack_status'],
                     status_reason=stack.get('stack_status_reason') or '',
                     outputs=outputs)

    def delete_stack(self, name):
        """Cancella lo stack; uno stack gia sparito non e un errore.

        Il rinvio di /stacks/{nome} vale solo per le letture: la
        cancellazione va fatta sull'indirizzo completo, con l'identificativo.
        """
        stack = self.get_stack(name)
        if stack is not None:
            self._delete_if_present(f'/stacks/{name}/{stack.id}')


def _heat_message(error):
    try:
        return error.response.json()['error']['message']
    except (AttributeError, KeyError, TypeError, ValueError):
        return _error_text(error)


@dataclasses.dataclass(frozen=True)
class Server:
    id: str
    status: str


class Nova(_Client):
    service_type = 'compute'

    def get_server(self, server_id):
        """La macchina, o None se non esiste piu.

        Heat non si accorge di una macchina cancellata o spenta da fuori:
        lo stack resta CREATE_COMPLETE, quindi la macchina va letta qui.
        """
        body = self._get_or_none(f'/servers/{server_id}')
        if body is None:
            return None
        return Server(id=body['server']['id'], status=body['server']['status'])
