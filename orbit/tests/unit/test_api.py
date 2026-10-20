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
        self.blazar = fakes.FakeBlazar()
        self.repository = fakes.repository()
        orbs = service.Orbs(self.repository, self._clients_for)
        self.client = app.create_app(orbs).test_client()

    def _clients_for(self, auth):
        self.assertEqual('auth-of-project-a', auth)
        return clients.Clients(blazar=self.blazar)

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

    def test_capacity_exhausted_is_409_and_leaves_no_orb(self):
        self.blazar.refuse_with = clients.CapacityExhausted('no room')

        response = self.create()

        self.assertEqual(409, response.status_code)
        self.assertEqual([], self.repository.list('project-a'))

    def test_unreachable_blazar_is_503(self):
        self.blazar.refuse_with = clients.Unavailable('reservation: down')

        self.assertEqual(503, self.create().status_code)

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
            {'image': ''},
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
