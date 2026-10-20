import unittest
from unittest import mock

from orbit import clients
from orbit import conf
from orbit import orb as orb_model
from orbit import service
from orbit.tests.unit import fakes

CONTEXT = service.Context('project-a', 'user-a', auth='auth')
REQUEST = service.CreateRequest(
    size=orb_model.Size(vcpus=2, memory_mb=4096, disk_gb=20),
    public_key=fakes.PUBLIC_KEY, image='cirros')


class TestCreate(unittest.TestCase):

    def setUp(self):
        conf.CONF([], project='orbit', default_config_files=[])
        self.addCleanup(conf.CONF.reset)
        self.blazar = fakes.FakeBlazar()
        self.repository = mock.Mock(wraps=fakes.repository())
        self.orbs = service.Orbs(
            self.repository, lambda auth: clients.Clients(blazar=self.blazar))

    def test_lease_is_deleted_when_the_orb_cannot_be_recorded(self):
        self.repository.add.side_effect = RuntimeError('database down')

        with self.assertRaises(RuntimeError):
            self.orbs.create(CONTEXT, REQUEST)

        self.assertEqual({}, self.blazar.leases)
