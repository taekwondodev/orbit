import unittest
from unittest import mock

from orbit import clients
from orbit import conf
from orbit import orb as orb_model
from orbit import service
from orbit.tests.unit import fakes

Status = orb_model.Status
CONTEXT = service.Context('project-a', 'user-a', auth='auth')
REQUEST = service.CreateRequest(
    size=orb_model.Size(vcpus=2, memory_mb=4096, disk_gb=20),
    public_key=fakes.PUBLIC_KEY, image='cirros')


class TestCreate(unittest.TestCase):

    def setUp(self):
        conf.CONF([], project='orbit', default_config_files=[])
        self.addCleanup(conf.CONF.reset)
        self.clients = fakes.fake_clients()
        self.blazar = self.clients.blazar
        self.creator = fakes.FakeCreator()
        self.repository = mock.Mock(wraps=fakes.repository())
        self.orbs = service.Orbs(self.repository, lambda auth: self.clients,
                                 self.creator)

    def test_lease_is_deleted_when_the_orb_cannot_be_recorded(self):
        self.repository.add.side_effect = RuntimeError('database down')

        with self.assertRaises(RuntimeError):
            self.orbs.create(CONTEXT, REQUEST)

        self.assertEqual({}, self.blazar.leases)
        self.assertEqual([], self.creator.started)


class ServiceTestCase(unittest.TestCase):

    def setUp(self):
        conf.CONF([], project='orbit', default_config_files=[])
        self.addCleanup(conf.CONF.reset)
        self.clients = fakes.fake_clients()
        self.blazar, self.heat = self.clients.blazar, self.clients.heat
        self.nova = self.clients.nova
        self.repository = fakes.repository()
        self.orbs = service.Orbs(self.repository, lambda auth: self.clients,
                                 fakes.FakeCreator())
        self.orb = self.orbs.create(CONTEXT, REQUEST).orb

    def build(self):
        """Porta l'orb fino a una macchina accesa, come farebbe il compito."""
        self.blazar.activate(self.orb.lease_id)
        stack_id = self.heat.create_stack(self.orb.resource_name, 't', {},
                                          'orbit')
        self.repository.update(self.orb.id, Status.RESERVING,
                               status=Status.BUILDING, stack_id=stack_id)
        self.heat.set_status(self.orb.resource_name, 'CREATE_COMPLETE',
                             ssh_host='172.24.4.17', server_id='server-1')
        self.nova.servers['server-1'] = clients.Server('server-1', 'ACTIVE')

    def stored(self):
        return self.repository.get('project-a', self.orb.id)


class TestRead(ServiceTestCase):

    def test_read_reports_reality_and_records_it(self):
        self.build()

        observed = self.orbs.get(CONTEXT, self.orb.id)

        self.assertEqual(Status.ACTIVE, observed.orb.status)
        self.assertEqual('172.24.4.17', observed.ssh_host)
        self.assertEqual(Status.ACTIVE, self.stored().status)

    def test_server_removed_from_outside_turns_the_orb_to_error(self):
        self.build()
        self.orbs.get(CONTEXT, self.orb.id)
        del self.nova.servers['server-1']

        observed = self.orbs.get(CONTEXT, self.orb.id)

        self.assertEqual(Status.ERROR, observed.orb.status)
        self.assertEqual('macchina non più disponibile', observed.orb.fault)
        self.assertIsNone(observed.ssh_host)

    def test_list_filters_on_the_observed_status(self):
        self.build()

        self.assertEqual([self.orb.id], [
            o.orb.id for o in self.orbs.list(CONTEXT, Status.ACTIVE)])
        self.assertEqual([], self.orbs.list(CONTEXT, Status.BUILDING))

    def test_unreachable_service_surfaces_as_unavailable(self):
        def down(lease_id):
            raise clients.Unavailable('reservation: down')
        self.blazar.get_lease = down

        with self.assertRaises(clients.Unavailable):
            self.orbs.get(CONTEXT, self.orb.id)


class TestDelete(ServiceTestCase):

    def test_delete_removes_stack_and_lease_then_reads_deleted(self):
        self.build()

        deleting = self.orbs.delete(CONTEXT, self.orb.id)
        deleted = self.orbs.get(CONTEXT, self.orb.id)

        self.assertEqual(Status.DELETING, deleting.orb.status)
        self.assertEqual({}, self.heat.stacks)
        self.assertEqual({}, self.blazar.leases)
        self.assertEqual(Status.DELETED, deleted.orb.status)
        self.assertIsNotNone(deleted.orb.deleted_at)

    def test_delete_is_repeatable(self):
        self.build()
        first = self.orbs.delete(CONTEXT, self.orb.id)

        second = self.orbs.delete(CONTEXT, self.orb.id)

        self.assertEqual(first.orb.status, second.orb.status)

    def test_delete_of_a_deleted_orb_answers_the_same_and_calls_nobody(self):
        self.orbs.delete(CONTEXT, self.orb.id)
        self.orbs.get(CONTEXT, self.orb.id)
        self.clients = None

        observed = self.orbs.delete(CONTEXT, self.orb.id)

        self.assertEqual(Status.DELETED, observed.orb.status)

    def test_delete_while_reserving_finds_a_stack_by_its_name(self):
        # Il compito di creazione ha creato lo stack ma non l'ha ancora
        # registrato: il nome deterministico lo ritrova.
        self.heat.create_stack(self.orb.resource_name, 't', {}, 'orbit')

        self.orbs.delete(CONTEXT, self.orb.id)

        self.assertEqual({}, self.heat.stacks)

    def test_unregistered_stack_still_deleting_keeps_the_orb_deleting(self):
        self.heat.create_stack(self.orb.resource_name, 't', {}, 'orbit')
        self.heat.delete_stack = lambda name: self.heat.set_status(
            name, 'DELETE_IN_PROGRESS')
        self.orbs.delete(CONTEXT, self.orb.id)

        observed = self.orbs.get(CONTEXT, self.orb.id)

        self.assertEqual(Status.DELETING, observed.orb.status)

    def test_error_orb_is_deleted_on_request(self):
        self.build()
        del self.nova.servers['server-1']
        self.orbs.get(CONTEXT, self.orb.id)

        observed = self.orbs.delete(CONTEXT, self.orb.id)

        self.assertEqual(Status.DELETING, observed.orb.status)
        self.assertIsNone(observed.orb.fault)

    def test_failed_stack_deletion_is_error_and_a_new_delete_retries(self):
        self.build()
        delete_stack = self.heat.delete_stack
        self.heat.delete_stack = lambda name: self.heat.set_status(
            name, 'DELETE_FAILED', 'Port in use')
        self.orbs.delete(CONTEXT, self.orb.id)
        self.assertEqual(Status.ERROR,
                         self.orbs.get(CONTEXT, self.orb.id).orb.status)
        self.heat.delete_stack = delete_stack

        self.orbs.delete(CONTEXT, self.orb.id)

        self.assertEqual(Status.DELETED,
                         self.orbs.get(CONTEXT, self.orb.id).orb.status)

    def test_unknown_orb_is_none(self):
        self.assertIsNone(self.orbs.delete(CONTEXT, 'missing'))
