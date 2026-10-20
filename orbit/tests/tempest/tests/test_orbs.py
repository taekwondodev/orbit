"""Il percorso completo di un orb su un'installazione reale."""

import time

import paramiko
from tempest import config
from tempest.lib.common import ssh
from tempest.lib import exceptions
from tempest import test

from orbit.tests.tempest import client

CONF = config.CONF


def _size(option):
    return {field: int(value) for field, value in option.items()}


def _key_pair():
    key = paramiko.RSAKey.generate(2048)
    return key, f'ssh-rsa {key.get_base64()} orbit-tempest'


class OrbsTest(test.BaseTestCase):

    credentials = ['primary', 'alt']

    @classmethod
    def skip_checks(cls):
        super().skip_checks()
        if not CONF.service_available.orbit:
            raise cls.skipException('orbit non e disponibile.')

    @classmethod
    def setup_clients(cls):
        super().setup_clients()
        cls.orbs = cls._orbs_client(cls.os_primary)
        cls.alt_orbs = cls._orbs_client(cls.os_alt)

    @staticmethod
    def _orbs_client(credentials):
        return client.OrbsClient(
            credentials.auth_provider, 'orbit', CONF.identity.region,
            build_timeout=CONF.orbit.build_timeout,
            build_interval=CONF.orbit.build_interval)

    def _wait_for(self, orb_id, status):
        deadline = time.time() + CONF.orbit.build_timeout
        while True:
            orb = self.orbs.show_orb(orb_id)
            if orb['status'] == status:
                return orb
            if orb['status'] == 'ERROR':
                self.fail(f"Orb {orb_id} in ERROR: {orb['fault']}")
            if time.time() > deadline:
                self.fail(f"Orb {orb_id} ancora in {orb['status']} dopo "
                          f"{CONF.orbit.build_timeout} secondi")
            time.sleep(CONF.orbit.build_interval)

    def _delete_quietly(self, orb_id):
        try:
            self.orbs.delete_orb(orb_id)
        except exceptions.NotFound:
            pass

    def test_orb_lifecycle(self):
        key, public_key = _key_pair()

        orb = self.orbs.create_orb(_size(CONF.orbit.size), public_key)
        self.addCleanup(self.orbs.wait_for_resource_deletion, orb['id'])
        self.addCleanup(self._delete_quietly, orb['id'])
        self.assertEqual('RESERVING', orb['status'])

        active = self._wait_for(orb['id'], 'ACTIVE')
        self.assertTrue(active['ssh_host'])
        self.assertRaises(exceptions.NotFound,
                          self.alt_orbs.show_orb, orb['id'])
        if CONF.orbit.ssh_check:
            ssh.Client(active['ssh_host'], active['ssh_user'], pkey=key,
                       timeout=CONF.orbit.build_timeout).exec_command('true')

        deleting = self.orbs.delete_orb(orb['id'])
        self.assertIn(deleting['status'], ('DELETING', 'DELETED'))
        self._wait_for(orb['id'], 'DELETED')
        self.assertEqual('DELETED', self.orbs.delete_orb(orb['id'])['status'])

    def test_size_no_host_can_hold_is_refused(self):
        _, public_key = _key_pair()
        before = self.orbs.list_orbs()['orbs']

        self.assertRaises(exceptions.Conflict, self.orbs.create_orb,
                          _size(CONF.orbit.oversized_size), public_key)

        self.assertEqual(before, self.orbs.list_orbs()['orbs'])
