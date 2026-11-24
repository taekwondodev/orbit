import dataclasses

from keystoneauth1 import adapter
from keystoneauth1 import exceptions as ks_exc
from keystoneauth1 import session as ks_session
from oslo_log import log

from orbit.conf import CONF

LOG = log.getLogger(__name__)


class Unavailable(Exception):
    """The message is generic: the original response, which may contain
    internal addresses or tracebacks, stays in ``detail`` and in the logs.
    """

    def __init__(self, service_type, detail):
        super().__init__(f'service {service_type} unreachable')
        self.detail = detail


class CapacityExhausted(Exception):
    pass


class Rejected(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


@dataclasses.dataclass(frozen=True)
class Clients:
    blazar: 'Blazar'
    heat: 'Heat'
    nova: 'Nova'


def for_auth(auth):
    session = ks_session.Session(auth=auth, timeout=CONF.orbs.api_timeout)
    return Clients(
        blazar=Blazar(session), heat=Heat(session), nova=Nova(session)
    )


class _Client:
    service_type = None

    def __init__(self, session):
        self._api = adapter.Adapter(
            session, service_type=self.service_type, interface='public'
        )

    def _call(self, method, url, missing_ok=False, **kwargs):
        try:
            return self._api.request(url, method, **kwargs)
        except ks_exc.NotFound as e:
            if missing_ok:
                raise
            raise Rejected(_message(e), e.http_status) from e
        except (ks_exc.RequestTimeout, ks_exc.TooManyRequests) as e:
            # 408 and 429 are transient: the caller retries as for a 5xx.
            raise Unavailable(self.service_type, _error_text(e)) from e
        except ks_exc.HTTPClientError as e:
            raise Rejected(_message(e), e.http_status) from e
        except (
            ks_exc.ConnectionError,
            ks_exc.EndpointNotFound,
            ks_exc.HttpServerError,
        ) as e:
            detail = _error_text(e)
            LOG.warning(
                '%s %s on %s: %s', method, url, self.service_type, detail
            )
            raise Unavailable(self.service_type, detail) from e

    def _get_or_none(self, url):
        try:
            return self._call('GET', url, missing_ok=True).json()
        except ks_exc.NotFound:
            return None

    def _delete_if_present(self, url):
        try:
            self._call('DELETE', url, missing_ok=True)
        except ks_exc.NotFound:
            pass


def _error_text(error):
    response = getattr(error, 'response', None)
    return response.text if response is not None else str(error)


def _message(error):
    # The formats of Heat, Blazar and Nova, in this order.
    try:
        body = error.response.json()
    except (AttributeError, ValueError):
        return _error_text(error)
    if isinstance(body.get('error'), dict) and 'message' in body['error']:
        return body['error']['message']
    if 'error_message' in body:
        return body['error_message']
    for value in body.values():
        if isinstance(value, dict) and 'message' in value:
            return value['message']
    return _error_text(error)


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

    # Blazar reports exhausted capacity with the NotEnoughHostsAvailable
    # exception, which declares no code: it arrives as a 500 and can only be
    # recognized by its message. Sources: blazar/manager/exceptions.py and
    # blazar/api/v1/utils.py.
    _CAPACITY_MESSAGE = 'Not enough hosts available'

    def create_lease(self, name, size, end_date):
        body = {
            'name': name,
            'start_date': 'now',
            'end_date': end_date,
            'reservations': [
                {
                    'resource_type': 'virtual:instance',
                    'vcpus': size.vcpus,
                    'memory_mb': size.memory_mb,
                    'disk_gb': size.disk_gb,
                    'amount': 1,
                    'affinity': None,
                    'resource_properties': '',
                }
            ],
            'events': [],
        }
        try:
            response = self._call('POST', '/leases', json=body)
        except Unavailable as e:
            if self._CAPACITY_MESSAGE in e.detail:
                raise CapacityExhausted(self._CAPACITY_MESSAGE) from e
            raise
        return _lease(response.json()['lease'])

    def get_lease(self, lease_id):
        body = self._get_or_none(f'/leases/{lease_id}')
        return _lease(body['lease']) if body else None

    def delete_lease(self, lease_id):
        self._delete_if_present(f'/leases/{lease_id}')


def _lease(body):
    reservation = body['reservations'][0]
    return Lease(
        id=body['id'],
        status=body['status'],
        reservation_id=reservation['id'],
        reservation_status=reservation['status'],
    )


@dataclasses.dataclass(frozen=True)
class Stack:
    id: str
    status: str
    status_reason: str
    outputs: dict


class Heat(_Client):
    service_type = 'orchestration'

    def create_stack(self, name, template, parameters, tag):
        body = {
            'stack_name': name,
            'template': template,
            'parameters': parameters,
            'tags': tag,
            # A failed stack stays up for diagnosis: only DELETE on the orb
            # deletes it (docs/design/api.md).
            'disable_rollback': True,
        }
        return self._call('POST', '/stacks', json=body).json()['stack']['id']

    def get_stack(self, name):
        # Heat answers /stacks/{name} with a redirect to /stacks/{name}/{id},
        # which keystoneauth follows.
        body = self._get_or_none(f'/stacks/{name}')
        if body is None or body['stack']['stack_status'] == 'DELETE_COMPLETE':
            return None
        stack = body['stack']
        outputs = {
            output['output_key']: output.get('output_value')
            for output in stack.get('outputs') or []
        }
        return Stack(
            id=stack['id'],
            status=stack['stack_status'],
            status_reason=stack.get('stack_status_reason') or '',
            outputs=outputs,
        )

    def delete_stack(self, name):
        # The /stacks/{name} redirect applies only to reads: the deletion must
        # target the full address, with the identifier.
        stack = self.get_stack(name)
        if stack is not None:
            self._delete_if_present(f'/stacks/{name}/{stack.id}')


@dataclasses.dataclass(frozen=True)
class Server:
    id: str
    status: str


class Nova(_Client):
    service_type = 'compute'

    def get_server(self, server_id):
        # Heat does not notice a machine deleted or stopped from outside: the
        # stack stays CREATE_COMPLETE, so the machine must be read here.
        body = self._get_or_none(f'/servers/{server_id}')
        if body is None:
            return None
        return Server(id=body['server']['id'], status=body['server']['status'])

    def get_console_output(self, server_id):
        # Nova keeps only the last part (100 KiB with libvirt): what the
        # machine printed at boot scrolls out on a chatty orb.
        response = self._call(
            'POST',
            f'/servers/{server_id}/action',
            json={'os-getConsoleOutput': {}},
        )
        return response.json()['output']
