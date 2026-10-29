from django.conf import settings
from django.contrib.staticfiles import finders
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
        self.assertNotIn('ajax-update', rows['orb-building'].classes)
        self.assertIn('warning', rows['orb-building'].classes)
        self.assertNotIn('warning', rows['orb-active'].classes)
        self.assertNotIn('warning', rows['orb-error'].classes)
        self.assertNotContains(res, 'orb-deleted')
        self.assertEqual(self.token.id,
                         self.orbit.last_request.headers['X-Auth-Token'])

    def test_empty_list_says_how_to_create_an_orb(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': []})

        res = self.client.get(INDEX_URL)

        self.assertContains(res, '<code>POST /v1/orbs</code>', html=True)

    def test_unavailable_orbit_shows_its_message_not_an_empty_project(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', status_code=503,
                       json={'error': {'message': 'Heat is unavailable'}})

        res = self.client.get(INDEX_URL)

        self.assertEqual(200, res.status_code)
        self.assertEqual([], res.context['table'].data)
        self.assertNotContains(res, 'POST /v1/orbs')
        self.assertMessageCount(res, error=1)
        self.assertIn('Heat is unavailable',
                      str(list(res.context['messages'])[0]))

    def test_live_list_discovers_orbs_and_updates_stable_rows(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', [
            {'json': {'orbs': []}},
            {'json': {'orbs': [_orb('orb-1', 'ACTIVE'),
                               _orb('orb-2', 'BUILDING')]}},
            {'json': {'orbs': [_orb('orb-1', 'ERROR'),
                               _orb('orb-2', 'DELETED')]}},
        ])

        page = self.client.get(INDEX_URL)
        self.assertContains(page, 'data-orbit-live')
        added = self.client.get(INDEX_URL, {'live': '1'},
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(200, added.status_code)
        self.assertIn('no-store', added['Cache-Control'])
        self.assertIn('orb-1', added.json()['html'])
        self.assertIn('orb-2', added.json()['html'])
        self.assertIn('Active', added.json()['html'])
        changed = self.client.get(INDEX_URL, {'live': '1'},
                                  HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIn('orb-1', changed.json()['html'])
        self.assertIn('Error', changed.json()['html'])
        self.assertNotIn('orb-2', changed.json()['html'])

    def test_live_failures_are_not_successful_empty_snapshots(self):
        detail_url = reverse('horizon:project:orbs:detail', args=['orb-1'])
        for url, resource in ((INDEX_URL, '/v1/orbs'),
                              (detail_url, '/v1/orbs/orb-1')):
            for status in (503, 401):
                with self.subTest(url=url, status=status):
                    self.orbit.get(
                        ORBIT + resource, status_code=status,
                        json={'error': {'message': 'Unavailable'}})
                    res = self.client.get(
                        url, {'live': '1'},
                        HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                    self.assertEqual(status, res.status_code)
                    self.assertNotIn('html', res.json())

    def test_expired_horizon_session_returns_401_without_a_snapshot(self):
        self.setActiveUser()
        detail_url = reverse('horizon:project:orbs:detail', args=['orb-1'])
        for url in (INDEX_URL, detail_url):
            with self.subTest(url=url):
                res = self.client.get(
                    url, {'live': '1'},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                self.assertEqual(401, res.status_code)
                self.assertEqual(b'', res.content)
        self.assertFalse(self.orbit.called)

    def test_live_script_is_registered_and_discoverable(self):
        self.assertIn('orbit/orbs-live.js', settings.HORIZON_CONFIG['js_files'])
        self.assertIsNotNone(finders.find('orbit/orbs-live.js'))


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

    def test_live_detail_updates_ssh_fault_and_deleted_status(self):
        url = reverse('horizon:project:orbs:detail', args=['orb-1'])
        self.orbit.get(f'{ORBIT}/v1/orbs/orb-1', [
            {'json': _orb('orb-1', 'BUILDING')},
            {'json': _orb('orb-1', 'ACTIVE', ssh_host='172.24.4.17')},
            {'json': _orb('orb-1', 'ERROR', fault='<failed>')},
            {'json': _orb('orb-1', 'DELETED')},
        ])
        self.assertContains(self.client.get(url), 'data-orbit-live')
        for expected in ('ssh ubuntu@172.24.4.17', '&lt;failed&gt;', 'Deleted'):
            res = self.client.get(url, {'live': '1'},
                                  HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            self.assertEqual(200, res.status_code)
            self.assertIn(expected, res.json()['html'])
            self.assertNotIn('<failed>', res.json()['html'])

    def test_live_unknown_orb_returns_not_found_without_redirecting(self):
        self.orbit.get(f'{ORBIT}/v1/orbs/orb-x', status_code=404,
                       json={'error': {'message': 'Orb not found'}})
        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['orb-x']),
            {'live': '1'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(404, res.status_code)
        self.assertNotIn('html', res.json())

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
