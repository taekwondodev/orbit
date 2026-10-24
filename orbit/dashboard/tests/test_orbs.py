from django.test import override_settings
from django.urls import reverse
import requests_mock

from openstack_dashboard.test import helpers

ORBIT = 'http://orbit.example.com/orbit'
INDEX_URL = reverse('horizon:project:orbs:index')


def _orb(orb_id, status, ssh_host=None, fault=None):
    return {'id': orb_id, 'status': status,
            'size': {'vcpus': 2, 'memory_mb': 4096, 'disk_gb': 20},
            'image': 'ubuntu-24.04', 'ssh_host': ssh_host,
            'ssh_user': 'ubuntu', 'fault': fault,
            'created_at': '2026-10-20T12:00:00'}


class OrbsTestCase(helpers.TestCase):

    def _setup_test_data(self):
        super()._setup_test_data()
        self.service_catalog.append(
            {'type': 'orbit', 'name': 'orbit', 'endpoints_links': [],
             'endpoints': [{'region': 'RegionOne', 'interface': 'public',
                            'url': ORBIT}]})

    def setUp(self):
        super().setUp()
        self.orbit = requests_mock.Mocker()
        self.orbit.start()
        self.addCleanup(self.orbit.stop)


class IndexTests(OrbsTestCase):

    def test_list_shows_the_orbs_that_still_exist(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': [
            _orb('orb-active', 'ACTIVE', ssh_host='172.24.4.17'),
            _orb('orb-building', 'BUILDING'),
            _orb('orb-error', 'ERROR', fault='Quota exceeded'),
            _orb('orb-deleted', 'DELETED'),
        ]})

        res = self.client.get(INDEX_URL)

        self.assertEqual(['orb-active', 'orb-building', 'orb-error'],
                         [orb.id for orb in res.context['table'].data])
        rows = {row.datum.id: row for row in res.context['table'].get_rows()}
        active = rows['orb-active'].cells
        self.assertEqual('Active', active['status'].data)
        self.assertEqual('172.24.4.17', active['ssh_host'].data)
        self.assertEqual('2 vCPU · 4096 MiB · 20 GiB', active['size'].data)
        self.assertIn('ajax-update', rows['orb-building'].classes)
        self.assertIn('warning', rows['orb-building'].classes)
        self.assertNotIn('warning', rows['orb-active'].classes)
        self.assertNotIn('warning', rows['orb-error'].classes)
        self.assertNotContains(res, 'orb-deleted')
        self.assertEqual(self.token.id,
                         self.orbit.last_request.headers['X-Auth-Token'])

    def test_empty_list_says_how_to_create_an_orb(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': []})

        res = self.client.get(INDEX_URL)

        self.assertContains(
            res, '<code>openstack orb create --vcpus 1 --memory 512 '
                 '--disk 1 --public-key ~/.ssh/id_ed25519.pub</code>',
            html=True)

    def test_unavailable_orbit_shows_its_message_not_an_empty_project(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', status_code=503,
                       json={'error': {'message': 'Heat is unavailable'}})

        res = self.client.get(INDEX_URL)

        self.assertEqual(200, res.status_code)
        self.assertEqual([], res.context['table'].data)
        self.assertNotContains(res, 'openstack orb create')
        self.assertMessageCount(res, error=1)
        self.assertIn('Heat is unavailable',
                      str(list(res.context['messages'])[0]))

    def test_row_of_an_orb_that_became_deleted_is_removed(self):
        self.orbit.get(f'{ORBIT}/v1/orbs/orb-1', json=_orb('orb-1', 'DELETED'))

        res = self.client.get(
            INDEX_URL, {'action': 'row_update', 'table': 'orbs',
                        'obj_id': 'orb-1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(404, res.status_code)


class DetailTests(OrbsTestCase):

    def test_active_orb_gives_the_ssh_command(self):
        self.orbit.get(f'{ORBIT}/v1/orbs/orb-1',
                       json=_orb('orb-1', 'ACTIVE', ssh_host='172.24.4.17'))

        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['orb-1']))

        self.assertContains(res, '<code>ssh ubuntu@172.24.4.17</code>',
                            html=True)

    def test_failed_orb_shows_its_fault_and_no_ssh_command(self):
        fault = 'Resource CREATE failed: Quota exceeded for instances'
        self.orbit.get(f'{ORBIT}/v1/orbs/orb-1',
                       json=_orb('orb-1', 'ERROR', fault=fault))

        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['orb-1']))

        self.assertContains(res, fault)
        self.assertNotContains(res, 'SSH command')

    def test_unknown_orb_redirects_to_the_list(self):
        self.orbit.get(f'{ORBIT}/v1/orbs/orb-x', status_code=404,
                       json={'error': {'message': 'Orb not found'}})

        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['orb-x']))

        self.assertRedirectsNoFollow(res, INDEX_URL)
        self.assertMessageCount(error=1)

    def test_dot_segment_id_is_an_unknown_orb(self):
        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['..']))

        self.assertRedirectsNoFollow(res, INDEX_URL)
        self.assertFalse(self.orbit.called)


class ClientTests(OrbsTestCase):

    @override_settings(OPENSTACK_SSL_CACERT='/etc/ssl/devstack-ca.pem')
    def test_requests_verify_with_horizons_ca_bundle(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': []})

        self.client.get(INDEX_URL)

        self.assertEqual('/etc/ssl/devstack-ca.pem',
                         self.orbit.last_request.verify)

    @override_settings(OPENSTACK_SSL_NO_VERIFY=True)
    def test_requests_skip_verification_when_horizon_does(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': []})

        self.client.get(INDEX_URL)

        self.assertIs(False, self.orbit.last_request.verify)

    def test_requests_give_up_after_30_seconds(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': []})

        self.client.get(INDEX_URL)

        self.assertEqual(30, self.orbit.last_request.timeout)
