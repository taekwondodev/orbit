import unittest

from orbit.api import app
from orbit import clients
from orbit import conf
from orbit import service
from orbit.tests.unit import fakes


class ApiTestCase(unittest.TestCase):

    def setUp(self):
        conf.CONF([], project='orbit', default_config_files=[])
        self.addCleanup(conf.CONF.reset)
        conf.CONF.set_override('default_image', 'cirros', 'orbs')
        conf.CONF.set_override('ssh_users', {'cirros': 'cirros'}, 'orbs')
        self.clients = fakes.fake_clients()
        self.auths = []
        self.blazar = self.clients.blazar
        self.creator = fakes.FakeCreator()
        self.repository = fakes.repository()
        orbs = service.Orbs(self.repository, self._clients_for, self.creator)
        self.client = app.create_app(orbs).test_client()

    def _clients_for(self, auth):
        self.auths.append(auth)
        return self.clients

    def request(self, method, path, project='project-a', **kwargs):
        environ = {'HTTP_X_PROJECT_ID': project, 'HTTP_X_USER_ID': 'user-a',
                   'keystone.token_auth': f'auth-of-{project}'}
        return self.client.open(path, method=method,
                                environ_overrides=environ, **kwargs)

    def create(self, **overrides):
        body = {'size': {'vcpus': 2, 'memory_mb': 4096, 'disk_gb': 20},
                'public_key': fakes.PUBLIC_KEY}
        body.update(overrides)
        return self.request('POST', '/v1/orbs', json=body)


class TestCreate(ApiTestCase):

    def test_accepted_orb_is_reserving_with_its_lease(self):
        response = self.create()

        self.assertEqual(202, response.status_code)
        orb = response.get_json()
        self.assertEqual('RESERVING', orb['status'])
        self.assertEqual({'vcpus': 2, 'memory_mb': 4096, 'disk_gb': 20},
                         orb['size'])
        self.assertEqual('cirros', orb['image'])
        self.assertEqual('cirros', orb['ssh_user'])
        self.assertIsNone(orb['ssh_host'])
        name, size, end_date = self.blazar.created[0]
        self.assertEqual(f"orbit-{orb['id']}", name)
        self.assertEqual('2099-12-31 23:59', end_date)
        stored = self.repository.get('project-a', orb['id'])
        self.assertEqual('lease-1', stored.lease_id)
        self.assertEqual('reservation-1', stored.reservation_id)
        self.assertEqual(size, stored.size)
        self.assertEqual([(stored, fakes.PUBLIC_KEY)], self.creator.started)
        self.assertEqual(['auth-of-project-a'], self.auths)

    def test_capacity_exhausted_is_409_and_leaves_no_orb(self):
        self.blazar.refuse_with = clients.CapacityExhausted('no room')

        response = self.create()

        self.assertEqual(409, response.status_code)
        self.assertEqual([], self.repository.list('project-a'))
        self.assertEqual([], self.creator.started)

    def test_unreachable_blazar_is_503_without_its_details(self):
        self.blazar.refuse_with = clients.Unavailable(
            'reservation', 'Traceback ... 10.0.0.5')

        response = self.create()

        self.assertEqual(503, response.status_code)
        self.assertNotIn('10.0.0.5', response.get_data(as_text=True))

    def test_refusals_downstream_are_json_errors(self):
        for code, expected in ((401, 401), (403, 403), (400, 502)):
            with self.subTest(code=code):
                self.blazar.refuse_with = clients.Rejected('no', code)

                response = self.create()

                self.assertEqual(expected, response.status_code)
                self.assertEqual(expected,
                                 response.get_json()['error']['code'])

    def test_invalid_requests_are_400_and_reserve_nothing(self):
        invalid = [
            {'size': None},
            {'size': {'vcpus': 2, 'memory_mb': 4096}},
            {'size': {'vcpus': 0, 'memory_mb': 4096, 'disk_gb': 20}},
            {'size': {'vcpus': 9, 'memory_mb': 4096, 'disk_gb': 20}},
            {'size': {'vcpus': True, 'memory_mb': 4096, 'disk_gb': 20}},
            {'size': {'vcpus': '2', 'memory_mb': 4096, 'disk_gb': 20}},
            {'public_key': None},
            {'public_key': 'not a key'},
            {'public_key': 'ssh-ed25519 not-base64!'},
            {'public_key': fakes.PUBLIC_KEY + '\nssh-ed25519 AAAA other'},
            {'public_key': 'ssh-rsa ' + 'A' * 9000},
            {'image': ''},
            {'image': 'x' * 256},
        ]
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                self.assertEqual(400, self.create(**overrides).status_code)
        self.assertEqual([], self.blazar.created)

    def test_without_image_and_default_the_request_is_400(self):
        conf.CONF.set_override('default_image', None, 'orbs')

        self.assertEqual(400, self.create().status_code)

    def test_non_json_body_is_400(self):
        response = self.request('POST', '/v1/orbs', data='size=2')

        self.assertEqual(400, response.status_code)


class TestRead(ApiTestCase):

    def test_orb_of_another_project_is_404(self):
        orb_id = self.create().get_json()['id']

        response = self.request('GET', f'/v1/orbs/{orb_id}',
                                project='project-b')

        self.assertEqual(404, response.status_code)

    def test_list_shows_only_the_project_orbs(self):
        orb_id = self.create().get_json()['id']

        mine = self.request('GET', '/v1/orbs').get_json()['orbs']
        theirs = self.request('GET', '/v1/orbs',
                              project='project-b').get_json()['orbs']

        self.assertEqual([orb_id], [orb['id'] for orb in mine])
        self.assertEqual([], theirs)

    def test_unknown_status_filter_is_400(self):
        response = self.request('GET', '/v1/orbs?status=SLEEPING')

        self.assertEqual(400, response.status_code)

    def test_token_without_project_is_403(self):
        response = self.request('GET', '/v1/orbs', project='')

        self.assertEqual(403, response.status_code)


class TestDelete(ApiTestCase):

    def test_delete_is_202_and_repeatable(self):
        orb_id = self.create().get_json()['id']

        first = self.request('DELETE', f'/v1/orbs/{orb_id}')
        second = self.request('DELETE', f'/v1/orbs/{orb_id}')

        self.assertEqual(202, first.status_code)
        self.assertEqual('DELETING', first.get_json()['status'])
        self.assertEqual(202, second.status_code)
        self.assertEqual(first.get_json(), second.get_json())

    def test_delete_of_another_project_orb_is_404(self):
        orb_id = self.create().get_json()['id']

        response = self.request('DELETE', f'/v1/orbs/{orb_id}',
                                project='project-b')

        self.assertEqual(404, response.status_code)
        self.assertEqual(1, len(self.blazar.leases))
