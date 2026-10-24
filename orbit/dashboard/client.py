"""Reads orbs from orbit with the token of the user logged into Horizon."""

from urllib import parse

from django.conf import settings
from keystoneauth1 import exceptions as ks_exc
from keystoneauth1 import session as ks_session
from openstack_dashboard.api import base

from orbit.dashboard.exceptions import OrbitError
from orbit.dashboard.exceptions import OrbitUnauthorized
from orbit.dashboard.exceptions import OrbNotFound

# Seconds to wait for orbit-api. Every list, detail and row refresh holds a
# Horizon worker while it waits; orbit-api bounds its own calls downstream.
TIMEOUT = 30


class Orb(base.APIDictWrapper):
    """An orb as GET /v1/orbs/{id} returns it (docs/design/api.md)."""


def orb_list(request):
    return [Orb(orb) for orb in _get(request, '/v1/orbs')['orbs']]


def orb_get(request, orb_id):
    # The HTTP client and the proxy in front of orbit resolve "." and "..",
    # even percent-encoded: such an id would address another resource.
    if orb_id in ('.', '..'):
        raise OrbNotFound(f'Orb {orb_id} not found')
    return Orb(_get(request, f"/v1/orbs/{parse.quote(orb_id, safe='')}"))


def _get(request, path):
    url = base.url_for(request, 'orbit').rstrip('/') + path
    session = ks_session.Session(verify=_verify(), timeout=TIMEOUT)
    try:
        return session.get(
            url, headers={'X-Auth-Token': request.user.token.id}).json()
    except ks_exc.Unauthorized as e:
        raise OrbitUnauthorized(_message(e)) from e
    except ks_exc.NotFound as e:
        raise OrbNotFound(_message(e)) from e
    except ks_exc.ClientException as e:
        raise OrbitError(_message(e)) from e


def _message(error):
    # orbit's errors carry {"error": {"message": ...}} (docs/design/api.md).
    try:
        return error.response.json()['error']['message']
    except (AttributeError, KeyError, TypeError, ValueError):
        return str(error)


def _verify():
    # The same TLS settings Horizon applies to its own API clients.
    if settings.OPENSTACK_SSL_NO_VERIFY:
        return False
    return settings.OPENSTACK_SSL_CACERT or True
