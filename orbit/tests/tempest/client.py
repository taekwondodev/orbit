import json

from tempest.lib.common import rest_client
from tempest.lib import exceptions


class OrbsClient(rest_client.RestClient):

    def create_orb(self, size, public_key, image=None):
        body = {'size': size, 'public_key': public_key}
        if image:
            body['image'] = image
        resp, body = self.post('v1/orbs', json.dumps(body))
        self.expected_success(202, resp.status)
        return rest_client.ResponseBody(resp, json.loads(body))

    def show_orb(self, orb_id):
        resp, body = self.get(f'v1/orbs/{orb_id}')
        self.expected_success(200, resp.status)
        return rest_client.ResponseBody(resp, json.loads(body))

    def list_orbs(self):
        resp, body = self.get('v1/orbs')
        self.expected_success(200, resp.status)
        return rest_client.ResponseBody(resp, json.loads(body))

    def delete_orb(self, orb_id):
        resp, body = self.delete(f'v1/orbs/{orb_id}')
        self.expected_success(202, resp.status)
        return rest_client.ResponseBody(resp, json.loads(body))

    def is_resource_deleted(self, orb_id):
        try:
            return self.show_orb(orb_id)['status'] == 'DELETED'
        except exceptions.NotFound:
            return True

    @property
    def resource_type(self):
        return 'orb'
