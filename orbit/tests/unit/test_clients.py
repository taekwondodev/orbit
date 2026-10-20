import unittest

from keystoneauth1 import session as ks_session
from keystoneauth1 import token_endpoint
import requests
import requests_mock

from orbit import clients
from orbit import orb as orb_model

# Come in DevStack, l'endpoint di Blazar nel catalogo include gia /v1.
BLAZAR = 'http://blazar.test/reservation/v1'
SIZE = orb_model.Size(vcpus=2, memory_mb=4096, disk_gb=20)


def _lease_body(status='PENDING', reservation_status='pending'):
    return {'lease': {'id': 'lease-1', 'status': status,
                      'reservations': [{'id': 'reservation-1',
                                        'status': reservation_status}]}}


class TestBlazar(unittest.TestCase):

    def setUp(self):
        session = ks_session.Session(
            auth=token_endpoint.Token(BLAZAR, 'user-token'))
        self.blazar = clients.Blazar(session)
        self.http = requests_mock.Mocker()
        self.http.start()
        self.addCleanup(self.http.stop)

    def test_lease_asks_the_size_from_now_until_the_given_end(self):
        self.http.post(f'{BLAZAR}/leases', json=_lease_body())

        lease = self.blazar.create_lease('orbit-1', SIZE, '2099-12-31 23:59')

        sent = self.http.last_request
        self.assertEqual('user-token', sent.headers['X-Auth-Token'])
        body = sent.json()
        self.assertEqual('orbit-1', body['name'])
        self.assertEqual('now', body['start_date'])
        self.assertEqual('2099-12-31 23:59', body['end_date'])
        self.assertEqual([{'resource_type': 'virtual:instance',
                           'vcpus': 2, 'memory_mb': 4096, 'disk_gb': 20,
                           'amount': 1, 'affinity': None,
                           'resource_properties': ''}],
                         body['reservations'])
        self.assertEqual(clients.Lease('lease-1', 'PENDING', 'reservation-1',
                                       'pending'), lease)

    def test_no_host_with_room_is_capacity_exhausted(self):
        self.http.post(f'{BLAZAR}/leases', status_code=500, json={
            'error_code': 500, 'error_name': 500,
            'error_message': 'Not enough hosts available'})

        with self.assertRaises(clients.CapacityExhausted):
            self.blazar.create_lease('orbit-1', SIZE, '2099-12-31 23:59')

    def test_other_server_errors_mean_unavailable(self):
        self.http.post(f'{BLAZAR}/leases', status_code=500, json={
            'error_code': 500, 'error_name': 'INTERNAL_SERVER_ERROR',
            'error_message': 'Internal Server Error'})

        with self.assertRaises(clients.Unavailable):
            self.blazar.create_lease('orbit-1', SIZE, '2099-12-31 23:59')

    def test_unreachable_blazar_means_unavailable(self):
        self.http.get(f'{BLAZAR}/leases/lease-1',
                      exc=requests.exceptions.ConnectionError)

        with self.assertRaises(clients.Unavailable):
            self.blazar.get_lease('lease-1')

    def test_active_reservation_makes_the_lease_active(self):
        self.http.get(f'{BLAZAR}/leases/lease-1',
                      json=_lease_body('ACTIVE', 'active'))

        self.assertTrue(self.blazar.get_lease('lease-1').is_active)

    def test_missing_lease_reads_as_none(self):
        self.http.get(f'{BLAZAR}/leases/lease-1', status_code=404)

        self.assertIsNone(self.blazar.get_lease('lease-1'))

    def test_deleting_a_missing_lease_is_not_an_error(self):
        self.http.delete(f'{BLAZAR}/leases/lease-1', status_code=404)

        self.blazar.delete_lease('lease-1')

        self.assertEqual('DELETE', self.http.last_request.method)


# Come in DevStack, l'endpoint di Heat nel catalogo include il progetto.
HEAT = 'http://heat.test/heat-api/v1/project-a'


def _stack_body(status='CREATE_COMPLETE', outputs=None):
    return {'stack': {'id': 'stack-1', 'stack_name': 'orbit-1',
                      'stack_status': status,
                      'stack_status_reason': 'Stack CREATE completed',
                      'outputs': outputs or []}}


class TestHeat(unittest.TestCase):

    def setUp(self):
        session = ks_session.Session(
            auth=token_endpoint.Token(HEAT, 'user-token'))
        self.heat = clients.Heat(session)
        self.http = requests_mock.Mocker()
        self.http.start()
        self.addCleanup(self.http.stop)

    def test_stack_is_created_tagged_and_kept_on_failure(self):
        self.http.post(f'{HEAT}/stacks', status_code=201,
                       json={'stack': {'id': 'stack-1'}})

        stack_id = self.heat.create_stack('orbit-1', 'template: yaml',
                                          {'orb_id': '1'}, 'orbit')

        self.assertEqual('stack-1', stack_id)
        self.assertEqual({'stack_name': 'orbit-1',
                          'template': 'template: yaml',
                          'parameters': {'orb_id': '1'},
                          'tags': 'orbit',
                          'disable_rollback': True},
                         self.http.last_request.json())

    def test_refused_stack_carries_the_heat_message(self):
        self.http.post(f'{HEAT}/stacks', status_code=400, json={
            'code': 400, 'title': 'Bad Request',
            'error': {'message': 'Parameter image is invalid',
                      'type': 'StackValidationFailed'}})

        with self.assertRaisesRegex(clients.Rejected,
                                    'Parameter image is invalid'):
            self.heat.create_stack('orbit-1', 't', {}, 'orbit')

    def test_stack_is_read_by_name_following_the_redirect(self):
        self.http.get(f'{HEAT}/stacks/orbit-1', status_code=302,
                      headers={'Location': f'{HEAT}/stacks/orbit-1/stack-1'})
        self.http.get(f'{HEAT}/stacks/orbit-1/stack-1', json=_stack_body(
            outputs=[{'output_key': 'ssh_host',
                      'output_value': '172.24.4.17'},
                     {'output_key': 'server_id', 'output_value': 'server-1'}]))

        stack = self.heat.get_stack('orbit-1')

        self.assertEqual(clients.Stack(
            id='stack-1', status='CREATE_COMPLETE',
            status_reason='Stack CREATE completed',
            outputs={'ssh_host': '172.24.4.17', 'server_id': 'server-1'}),
            stack)

    def test_missing_or_deleted_stack_reads_as_none(self):
        self.http.get(f'{HEAT}/stacks/orbit-1', status_code=404)
        self.assertIsNone(self.heat.get_stack('orbit-1'))

        self.http.get(f'{HEAT}/stacks/orbit-1',
                      json=_stack_body('DELETE_COMPLETE'))
        self.assertIsNone(self.heat.get_stack('orbit-1'))

    def test_delete_uses_the_full_stack_address(self):
        self.http.get(f'{HEAT}/stacks/orbit-1', json=_stack_body())
        self.http.delete(f'{HEAT}/stacks/orbit-1/stack-1', status_code=204)

        self.heat.delete_stack('orbit-1')

        self.assertEqual('DELETE', self.http.last_request.method)
        self.assertEqual(f'{HEAT}/stacks/orbit-1/stack-1',
                         self.http.last_request.url)

    def test_deleting_a_missing_stack_is_not_an_error(self):
        self.http.get(f'{HEAT}/stacks/orbit-1', status_code=404)

        self.heat.delete_stack('orbit-1')

        self.assertEqual('GET', self.http.last_request.method)
