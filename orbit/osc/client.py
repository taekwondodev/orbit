"""orbit API client for the ``openstack orb`` commands."""

from keystoneauth1 import adapter
from keystoneauth1 import exceptions as ks_exc
from osc_lib import exceptions


class Client:

    def __init__(self, session, region_name=None, interface=None):
        self._api = adapter.Adapter(session, service_type='orbit',
                                    region_name=region_name,
                                    interface=interface)

    def create(self, size, public_key, ssh_allowed_cidr, image=None):
        body = {'size': size, 'public_key': public_key,
                'ssh_allowed_cidr': ssh_allowed_cidr}
        if image:
            body['image'] = image
        return self._request('POST', '/v1/orbs', json=body)

    def list(self, status=None):
        params = {'status': status} if status else None
        return self._request('GET', '/v1/orbs', params=params)['orbs']

    def get(self, orb_id):
        return self._request('GET', f'/v1/orbs/{orb_id}')

    def delete(self, orb_id):
        return self._request('DELETE', f'/v1/orbs/{orb_id}')

    def _request(self, method, url, **kwargs):
        try:
            return self._api.request(url, method, **kwargs).json()
        except ks_exc.HttpError as e:
            raise exceptions.CommandError(_message(e)) from e


def _message(error):
    try:
        return error.response.json()['error']['message']
    except (AttributeError, KeyError, TypeError, ValueError):
        return str(error)
