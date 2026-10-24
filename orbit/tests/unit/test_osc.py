import argparse
import io
import tempfile
import unittest
from unittest import mock

from keystoneauth1 import session as ks_session
from keystoneauth1 import token_endpoint
from osc_lib import exceptions
import requests_mock

from orbit.osc import client as orbit_client
from orbit.osc import v1
from orbit.tests.unit import fakes

ORBIT = 'http://orbit.test/orbit'
ORB = {'id': 'orb-1', 'status': 'ACTIVE',
       'size': {'vcpus': 2, 'memory_mb': 4096, 'disk_gb': 20},
       'image': 'cirros', 'ssh_host': '172.24.4.17', 'ssh_user': 'cirros',
       'ssh_host_keys': [fakes.HOST_KEY_ECDSA, fakes.HOST_KEY_ED25519],
       'fault': None, 'created_at': '2026-10-20T12:00:00'}


class TestClient(unittest.TestCase):

    def setUp(self):
        session = ks_session.Session(
            auth=token_endpoint.Token(ORBIT, 'user-token'))
        self.client = orbit_client.Client(session)
        self.http = requests_mock.Mocker()
        self.http.start()
        self.addCleanup(self.http.stop)

    def test_create_sends_size_key_and_image(self):
        self.http.post(f'{ORBIT}/v1/orbs', status_code=202, json=ORB)

        self.client.create({'vcpus': 2, 'memory_mb': 4096, 'disk_gb': 20},
                           fakes.PUBLIC_KEY, 'cirros')

        self.assertEqual({'size': {'vcpus': 2, 'memory_mb': 4096,
                                   'disk_gb': 20},
                          'public_key': fakes.PUBLIC_KEY,
                          'image': 'cirros'},
                         self.http.last_request.json())

    def test_list_passes_the_status_filter(self):
        self.http.get(f'{ORBIT}/v1/orbs?status=ACTIVE', json={'orbs': [ORB]})

        self.assertEqual([ORB], self.client.list('ACTIVE'))

    def test_service_errors_become_command_errors_with_their_message(self):
        self.http.post(f'{ORBIT}/v1/orbs', status_code=409, json={
            'error': {'code': 409, 'message': 'Capacita esaurita'}})

        with self.assertRaisesRegex(exceptions.CommandError,
                                    'Capacita esaurita'):
            self.client.create({}, fakes.PUBLIC_KEY)


class CommandTestCase(unittest.TestCase):

    def setUp(self):
        self.orbit = mock.Mock()
        self.app = mock.Mock(stderr=io.StringIO())
        self.app.client_manager.orbit = self.orbit

    def run_command(self, command_class, argv):
        command = command_class(self.app, argparse.Namespace())
        parsed = command.get_parser('openstack').parse_args(argv)
        return command.take_action(parsed)


class TestCommands(CommandTestCase):

    def test_create_reads_the_key_file_and_shows_the_orb(self):
        self.orbit.create.return_value = ORB
        with tempfile.NamedTemporaryFile('w', suffix='.pub') as key:
            key.write(fakes.PUBLIC_KEY + '\n')
            key.flush()

            columns, row = self.run_command(v1.CreateOrb, [
                '--vcpus', '2', '--memory', '4096', '--disk', '20',
                '--public-key', key.name])

        self.orbit.create.assert_called_once_with(
            {'vcpus': 2, 'memory_mb': 4096, 'disk_gb': 20},
            fakes.PUBLIC_KEY + '\n', None)
        self.assertEqual('172.24.4.17', dict(zip(columns, row))['ssh_host'])

    def test_create_with_a_missing_key_file_is_a_command_error(self):
        with self.assertRaises(exceptions.CommandError):
            self.run_command(v1.CreateOrb, [
                '--vcpus', '2', '--memory', '4096', '--disk', '20',
                '--public-key', '/nonexistent/key.pub'])
        self.orbit.create.assert_not_called()

    def test_wait_polls_until_a_final_status(self):
        building = dict(ORB, status='BUILDING')
        client = mock.Mock()
        client.get.side_effect = [building, ORB]

        orb = v1._wait(client, dict(ORB, status='RESERVING'),
                       sleep=lambda seconds: None)

        self.assertEqual('ACTIVE', orb['status'])
        self.assertEqual(2, client.get.call_count)

    def test_create_wait_ending_in_error_is_a_command_error(self):
        self.orbit.create.return_value = dict(
            ORB, status='ERROR', fault='Quota exceeded')
        with tempfile.NamedTemporaryFile('w', suffix='.pub') as key:
            key.write(fakes.PUBLIC_KEY)
            key.flush()

            with self.assertRaisesRegex(exceptions.CommandError,
                                        'orb-1 .*ERROR.*Quota exceeded'):
                self.run_command(v1.CreateOrb, [
                    '--vcpus', '2', '--memory', '4096', '--disk', '20',
                    '--public-key', key.name, '--wait'])

    def test_show_prints_the_host_keys(self):
        self.orbit.get.return_value = ORB

        columns, row = self.run_command(v1.ShowOrb, ['orb-1'])

        keys = dict(zip(columns, row))['ssh_host_keys']
        self.assertEqual([fakes.HOST_KEY_ECDSA, fakes.HOST_KEY_ED25519],
                         keys.machine_readable())
        self.assertEqual(f'{fakes.HOST_KEY_ECDSA}, {fakes.HOST_KEY_ED25519}',
                         keys.human_readable())

    def test_list_flattens_the_size(self):
        self.orbit.list.return_value = [ORB]

        columns, rows = self.run_command(v1.ListOrb, [])

        self.assertEqual([('orb-1', 'ACTIVE', 2, 4096, 20, '172.24.4.17')],
                         rows)

    def test_delete_continues_past_failures_and_reports_them(self):
        self.orbit.delete.side_effect = [
            exceptions.CommandError('not found'), ORB]

        with self.assertRaises(exceptions.CommandError):
            self.run_command(v1.DeleteOrb, ['missing', 'orb-1'])

        self.assertEqual(2, self.orbit.delete.call_count)
