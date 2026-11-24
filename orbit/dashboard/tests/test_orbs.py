import datetime

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
import requests_mock

from openstack_dashboard.test import helpers

from orbit.dashboard import client
from orbit.dashboard.orbs import overview

ORBIT = 'http://orbit.example.com/orbit'
INDEX_URL = reverse('horizon:project:orbs:index')


def _orb(
    orb_id,
    status,
    ssh_host=None,
    fault=None,
    created_at='2026-10-20T12:00:00',
    vcpus=2,
):
    return {
        'id': orb_id,
        'status': status,
        'size': {'vcpus': vcpus, 'memory_mb': 4096, 'disk_gb': 20},
        'ssh_host': ssh_host,
        'ssh_user': 'ubuntu',
        'fault': fault,
        'created_at': created_at,
    }


class OrbsTestCase(helpers.TestCase):
    def _setup_test_data(self):
        super()._setup_test_data()
        self.service_catalog.append(
            {
                'type': 'orbit',
                'name': 'orbit',
                'endpoints_links': [],
                'endpoints': [
                    {
                        'region': 'RegionOne',
                        'interface': 'public',
                        'url': ORBIT,
                    }
                ],
            }
        )

    def setUp(self):
        super().setUp()
        self.orbit = requests_mock.Mocker()
        self.orbit.start()
        self.addCleanup(self.orbit.stop)


class IndexTests(OrbsTestCase):
    def test_list_shows_the_orbs_that_still_exist_failures_first(self):
        self.orbit.get(
            f'{ORBIT}/v1/orbs',
            json={
                'orbs': [
                    _orb('orb-active', 'ACTIVE', ssh_host='172.24.4.17'),
                    _orb('orb-building', 'BUILDING'),
                    _orb('orb-error', 'ERROR', fault='<Quota exceeded>'),
                    _orb('orb-deleted', 'DELETED'),
                ]
            },
        )

        res = self.client.get(INDEX_URL)

        self.assertEqual(
            ['orb-error', 'orb-building', 'orb-active'],
            [orb.id for orb in res.context['table'].data],
        )
        rows = {row.datum.id: row for row in res.context['table'].get_rows()}
        active = rows['orb-active']
        self.assertIn('Active', active.cells['status'].data)
        self.assertEqual('ACTIVE', active.attrs['data-orbit-status'])
        self.assertNotIn('ssh_host', active.cells)
        self.assertIn('orbit-row-error', rows['orb-error'].classes)
        for row in rows.values():
            self.assertNotIn('ajax-update', row.classes)
            self.assertNotIn('warning', row.classes)
        self.assertContains(
            res, '<span class="orbit-chip"><b>4096</b> MiB</span>', html=True
        )
        self.assertContains(res, '&lt;Quota exceeded&gt;')
        self.assertNotContains(res, '<Quota exceeded>')
        self.assertContains(
            res, reverse('horizon:project:orbs:detail', args=['orb-error'])
        )
        self.assertNotContains(res, 'orb-deleted')
        self.assertEqual(
            self.token.id, self.orbit.last_request.headers['X-Auth-Token']
        )

    def test_orbs_on_their_way_up_show_a_pulsing_badge_and_their_step(self):
        self.orbit.get(
            f'{ORBIT}/v1/orbs',
            json={
                'orbs': [
                    _orb('orb-reserving', 'RESERVING'),
                    _orb('orb-active', 'ACTIVE', ssh_host='172.24.4.17'),
                    _orb('orb-error', 'ERROR', fault='Quota exceeded'),
                ]
            },
        )

        res = self.client.get(INDEX_URL)

        rows = {row.datum.id: row for row in res.context['table'].get_rows()}
        reserving = str(rows['orb-reserving'].cells['status'].data)
        self.assertIn('orbit-pulse', reserving)
        self.assertEqual(1, reserving.count('orbit-step-now'))
        self.assertEqual(2, reserving.count('orbit-step-todo'))
        active = str(rows['orb-active'].cells['status'].data)
        self.assertNotIn('orbit-pulse', active)
        self.assertEqual(3, active.count('orbit-step-done'))
        # orbit does not say which step failed.
        self.assertNotIn(
            'orbit-steps', str(rows['orb-error'].cells['status'].data)
        )

    def test_summary_counts_the_project_including_deleted_history(self):
        today = timezone.localdate()
        self.orbit.get(
            f'{ORBIT}/v1/orbs',
            json={
                'orbs': [
                    _orb(
                        'orb-active', 'ACTIVE', created_at=f'{today}T12:00:00'
                    ),
                    _orb('orb-error', 'ERROR', fault='Quota exceeded'),
                    _orb(
                        'orb-deleted',
                        'DELETED',
                        created_at=f'{today}T11:00:00',
                    ),
                ]
            },
        )

        res = self.client.get(INDEX_URL)

        summary = res.context['overview']
        self.assertEqual(
            {'active': 1, 'starting': 0, 'error': 1, 'deleting': 0},
            {group.key: group.count for group in summary.groups},
        )
        self.assertEqual(4, summary.vcpus)
        self.assertEqual(2, summary.days[-1].count)
        self.assertContains(res, 'class="orbit-overview"')
        self.assertContains(res, 'Resources held')
        # The bars are drawn for the eye; the counts are read as a list.
        self.assertContains(
            res, f'<li>{today:%Y-%m-%d}: 2 orbs created</li>', html=True
        )
        self.assertContains(res, '<div class="orbit-bars" aria-hidden="true">')

    def test_panel_reads_in_english_whatever_the_users_language(self):
        # The list shows an age, the detail a date: Django's own Italian
        # catalog translates both. Horizon ships its catalogs uncompiled.
        created = timezone.now() - datetime.timedelta(days=15)
        listed = _orb(
            'orb-1',
            'ACTIVE',
            ssh_host='172.24.4.17',
            created_at=created.strftime('%Y-%m-%dT%H:%M:%S'),
        )
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': [listed]})
        self.orbit.get(
            f'{ORBIT}/v1/orbs/orb-1',
            json=_orb(
                'orb-1',
                'ACTIVE',
                ssh_host='172.24.4.17',
                created_at='2026-10-20T12:00:00',
            ),
        )
        detail_url = reverse('horizon:project:orbs:detail', args=['orb-1'])
        expected = {
            INDEX_URL: ('2\xa0weeks', '2\xa0settimane'),
            detail_url: ('Oct. 20, 2026', '20 Ottobre 2026'),
        }

        for url, (english, italian) in expected.items():
            for live in ({}, {'live': '1'}):
                with self.subTest(url=url, live=live):
                    res = self.client.get(
                        url,
                        live,
                        HTTP_ACCEPT_LANGUAGE='it',
                        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                    )
                    html = (
                        res.json()['html'] if live else (res.content.decode())
                    )
                    self.assertIn(english, html)
                    self.assertNotIn(italian, html)

    def test_empty_list_says_how_to_create_an_orb(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': []})

        res = self.client.get(INDEX_URL)

        self.assertContains(res, '<code>POST /v1/orbs</code>', html=True)

    def test_unavailable_orbit_shows_its_message_not_an_empty_project(self):
        self.orbit.get(
            f'{ORBIT}/v1/orbs',
            status_code=503,
            json={'error': {'message': 'Heat is unavailable'}},
        )

        res = self.client.get(INDEX_URL)

        self.assertEqual(200, res.status_code)
        self.assertEqual([], res.context['table'].data)
        self.assertNotContains(res, 'POST /v1/orbs')
        # No summary: zero orbs would be false.
        self.assertNotIn('overview', res.context)
        self.assertNotContains(res, 'orbit-overview')
        self.assertMessageCount(res, error=1)
        self.assertIn(
            'Heat is unavailable', str(list(res.context['messages'])[0])
        )

    def test_live_list_discovers_orbs_and_updates_stable_rows(self):
        self.orbit.get(
            f'{ORBIT}/v1/orbs',
            [
                {'json': {'orbs': []}},
                {
                    'json': {
                        'orbs': [
                            _orb('orb-1', 'ACTIVE'),
                            _orb('orb-2', 'BUILDING'),
                        ]
                    }
                },
                {
                    'json': {
                        'orbs': [
                            _orb('orb-1', 'ERROR'),
                            _orb('orb-2', 'DELETED'),
                        ]
                    }
                },
            ],
        )

        page = self.client.get(INDEX_URL)
        self.assertContains(page, 'data-orbit-live')
        added = self.client.get(
            INDEX_URL, {'live': '1'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(200, added.status_code)
        self.assertIn('no-store', added['Cache-Control'])
        self.assertIn('orb-1', added.json()['html'])
        self.assertIn('orb-2', added.json()['html'])
        self.assertIn('Active', added.json()['html'])
        self.assertIn('orbit-overview', added.json()['html'])
        self.assertIn('data-orbit-status="BUILDING"', added.json()['html'])
        changed = self.client.get(
            INDEX_URL, {'live': '1'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertIn('orb-1', changed.json()['html'])
        self.assertIn('Error', changed.json()['html'])
        self.assertNotIn('orb-2', changed.json()['html'])

    def test_live_failures_are_not_successful_empty_snapshots(self):
        detail_url = reverse('horizon:project:orbs:detail', args=['orb-1'])
        for url, resource in (
            (INDEX_URL, '/v1/orbs'),
            (detail_url, '/v1/orbs/orb-1'),
        ):
            for status in (503, 401):
                with self.subTest(url=url, status=status):
                    self.orbit.get(
                        ORBIT + resource,
                        status_code=status,
                        json={'error': {'message': 'Unavailable'}},
                    )
                    res = self.client.get(
                        url,
                        {'live': '1'},
                        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                    )
                    self.assertEqual(status, res.status_code)
                    self.assertNotIn('html', res.json())

    def test_expired_horizon_session_returns_401_without_a_snapshot(self):
        self.setActiveUser()
        detail_url = reverse('horizon:project:orbs:detail', args=['orb-1'])
        for url in (INDEX_URL, detail_url):
            with self.subTest(url=url):
                res = self.client.get(
                    url, {'live': '1'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
                )
                self.assertEqual(401, res.status_code)
                self.assertEqual(b'', res.content)
        self.assertFalse(self.orbit.called)

    def test_live_script_and_styles_are_registered_and_discoverable(self):
        self.assertIn(
            'orbit/orbs-live.js', settings.HORIZON_CONFIG['js_files']
        )
        self.assertIsNotNone(finders.find('orbit/orbs-live.js'))
        self.assertIn('orbit/orbs.scss', settings.HORIZON_CONFIG['scss_files'])
        self.assertIsNotNone(finders.find('orbit/orbs.scss'))


class OverviewTests(helpers.TestCase):
    TODAY = datetime.date(2026, 10, 20)

    def _summarize(self, *orbs):
        with timezone.override('UTC'):
            return overview.summarize(
                [client.Orb(orb) for orb in orbs], self.TODAY
            )

    def test_reserved_resources_count_every_orb_until_deleted(self):
        summary = self._summarize(
            _orb('a', 'RESERVING', vcpus=1),
            _orb('b', 'ACTIVE', vcpus=2),
            _orb('c', 'ERROR', vcpus=4),
            _orb('d', 'DELETING', vcpus=8),
            _orb('e', 'DELETED', vcpus=16),
        )

        self.assertEqual(15, summary.vcpus)
        self.assertEqual(16, summary.memory_gib)
        self.assertEqual(80, summary.disk_gb)
        self.assertEqual(
            {'active': 1, 'starting': 1, 'error': 1, 'deleting': 1},
            {group.key: group.count for group in summary.groups},
        )

    def test_activity_counts_creations_per_day_over_two_weeks(self):
        summary = self._summarize(
            _orb('today-1', 'ACTIVE', created_at='2026-10-20T00:30:00'),
            _orb('today-2', 'DELETED', created_at='2026-10-20T23:59:00'),
            _orb('week', 'DELETED', created_at='2026-10-14T08:00:00'),
            _orb('older', 'DELETED', created_at='2026-10-13T08:00:00'),
            _orb('window', 'DELETED', created_at='2026-10-07T08:00:00'),
            _orb('outside', 'DELETED', created_at='2026-10-06T23:00:00'),
        )

        self.assertEqual(14, len(summary.days))
        self.assertEqual(datetime.date(2026, 10, 7), summary.days[0].date)
        self.assertEqual(self.TODAY, summary.days[-1].date)
        self.assertEqual(
            [1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 2],
            [day.count for day in summary.days],
        )
        self.assertEqual(3, summary.created_last_week)
        self.assertEqual(100, summary.days[-1].percent)
        self.assertEqual(50, summary.days[0].percent)

    def test_days_follow_the_users_time_zone(self):
        orb = _orb('late', 'ACTIVE', created_at='2026-10-19T23:30:00')
        with timezone.override('Europe/Rome'):
            summary = overview.summarize([client.Orb(orb)], self.TODAY)

        self.assertEqual(1, summary.days[-1].count)


class DetailTests(OrbsTestCase):
    def test_active_orb_shows_its_address_without_a_partial_command(self):
        self.orbit.get(
            f'{ORBIT}/v1/orbs/orb-1',
            json=_orb('orb-1', 'ACTIVE', ssh_host='172.24.4.17'),
        )

        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['orb-1'])
        )

        self.assertContains(res, '172.24.4.17')
        self.assertContains(res, 'ubuntu')
        # Without the client's private key the bare command fails.
        self.assertNotContains(res, 'ssh ubuntu@')
        self.assertContains(res, 'private key')
        self.assertEqual(
            ['done', 'done', 'done'],
            [step['state'] for step in res.context['steps']],
        )

    def test_building_orb_shows_the_step_it_waits_for(self):
        self.orbit.get(
            f'{ORBIT}/v1/orbs/orb-1', json=_orb('orb-1', 'BUILDING')
        )

        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['orb-1'])
        )

        self.assertEqual(
            ['done', 'now', 'todo'],
            [step['state'] for step in res.context['steps']],
        )
        self.assertContains(res, 'orbit-pulse')
        self.assertContains(res, 'aria-current="step"', count=1)
        for state in ('(completed)', '(current)', '(pending)'):
            self.assertContains(res, state, count=1)

    def test_failed_orb_shows_its_fault_and_no_ssh_command(self):
        fault = 'Resource CREATE failed: Quota exceeded for instances'
        self.orbit.get(
            f'{ORBIT}/v1/orbs/orb-1', json=_orb('orb-1', 'ERROR', fault=fault)
        )

        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['orb-1'])
        )

        self.assertContains(res, fault)
        self.assertContains(res, 'resources stay allocated for diagnosis')
        self.assertNotIn('steps', res.context)

    def test_live_detail_updates_ssh_fault_and_deleted_status(self):
        url = reverse('horizon:project:orbs:detail', args=['orb-1'])
        self.orbit.get(
            f'{ORBIT}/v1/orbs/orb-1',
            [
                {'json': _orb('orb-1', 'BUILDING')},
                {'json': _orb('orb-1', 'ACTIVE', ssh_host='172.24.4.17')},
                {'json': _orb('orb-1', 'ERROR', fault='<failed>')},
                {'json': _orb('orb-1', 'DELETED')},
            ],
        )
        self.assertContains(self.client.get(url), 'data-orbit-live')
        for expected in ('172.24.4.17', '&lt;failed&gt;', 'Deleted'):
            res = self.client.get(
                url, {'live': '1'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(200, res.status_code)
            self.assertIn(expected, res.json()['html'])
            self.assertNotIn('<failed>', res.json()['html'])

    def test_live_unknown_orb_returns_not_found_without_redirecting(self):
        self.orbit.get(
            f'{ORBIT}/v1/orbs/orb-x',
            status_code=404,
            json={'error': {'message': 'Orb not found'}},
        )
        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['orb-x']),
            {'live': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(404, res.status_code)
        self.assertNotIn('html', res.json())

    def test_unknown_orb_redirects_to_the_list(self):
        self.orbit.get(
            f'{ORBIT}/v1/orbs/orb-x',
            status_code=404,
            json={'error': {'message': 'Orb not found'}},
        )

        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['orb-x'])
        )

        self.assertRedirectsNoFollow(res, INDEX_URL)
        self.assertMessageCount(error=1)

    def test_dot_segment_id_is_an_unknown_orb(self):
        res = self.client.get(
            reverse('horizon:project:orbs:detail', args=['..'])
        )

        self.assertRedirectsNoFollow(res, INDEX_URL)
        self.assertFalse(self.orbit.called)


class ClientTests(OrbsTestCase):
    @override_settings(OPENSTACK_SSL_CACERT='/etc/ssl/devstack-ca.pem')
    def test_requests_verify_with_horizons_ca_bundle(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': []})

        self.client.get(INDEX_URL)

        self.assertEqual(
            '/etc/ssl/devstack-ca.pem', self.orbit.last_request.verify
        )

    @override_settings(OPENSTACK_SSL_NO_VERIFY=True)
    def test_requests_skip_verification_when_horizon_does(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': []})

        self.client.get(INDEX_URL)

        self.assertIs(False, self.orbit.last_request.verify)

    def test_requests_give_up_after_30_seconds(self):
        self.orbit.get(f'{ORBIT}/v1/orbs', json={'orbs': []})

        self.client.get(INDEX_URL)

        self.assertEqual(30, self.orbit.last_request.timeout)
