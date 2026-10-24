import datetime
import unittest

import yaml

from orbit import clients
from orbit import conf
from orbit import creation
from orbit import orb as orb_model
from orbit.tests.unit import fakes

Status = orb_model.Status
START = datetime.datetime(2026, 10, 20, 12, 0, 0)


class FakeClock:
    """Time advances only when the task waits."""

    def __init__(self):
        self.now = START

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += datetime.timedelta(seconds=seconds)


class TestCreator(unittest.TestCase):

    def setUp(self):
        conf.CONF([], project='orbit', default_config_files=[])
        self.addCleanup(conf.CONF.reset)
        conf.CONF.set_override('ssh_allowed_cidr', '198.51.100.20/32', 'orbs')
        self.clients = fakes.fake_clients()
        self.blazar, self.heat = self.clients.blazar, self.clients.heat
        self.repository = fakes.repository()
        self.clock = FakeClock()
        self.creator = creation.Creator(self.repository, 'template-text',
                                        sleep=self.clock.sleep,
                                        clock=self.clock)
        lease = self.blazar.create_lease('orbit-x', None, None)
        self.orb = fakes.orb(lease_id=lease.id,
                             reservation_id=lease.reservation_id,
                             created_at=START)
        self.repository.add(self.orb)

    def stored(self):
        return self.repository.get(self.orb.project_id, self.orb.id)

    def activate_after(self, polls):
        get_lease = self.blazar.get_lease
        calls = []

        def counting(lease_id):
            calls.append(lease_id)
            if len(calls) == polls:
                self.blazar.activate(lease_id)
            return get_lease(lease_id)
        self.blazar.get_lease = counting

    def test_stack_is_created_once_the_reservation_is_active(self):
        self.activate_after(polls=3)

        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

        name, template, parameters, tag = self.heat.created[0]
        self.assertEqual(self.orb.resource_name, name)
        self.assertEqual('template-text', template)
        self.assertEqual('orbit', tag)
        self.assertEqual({'orb_id': self.orb.id,
                          'reservation_id': self.orb.reservation_id,
                          'image': 'cirros',
                          'public_key': fakes.PUBLIC_KEY,
                          'public_network': 'public',
                          'ssh_allowed_cidr': '198.51.100.20/32'}, parameters)
        self.assertEqual(Status.BUILDING, self.stored().status)
        self.assertEqual('stack-1', self.stored().stack_id)
        self.assertEqual(START + datetime.timedelta(seconds=4),
                         self.clock.now)

    def test_gives_up_without_a_stack_at_the_timeout(self):
        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

        self.assertEqual([], self.heat.created)
        self.assertEqual(Status.RESERVING, self.stored().status)
        self.assertEqual(START + datetime.timedelta(seconds=120),
                         self.clock.now)

    def test_failed_reservation_creates_no_stack(self):
        self.blazar.leases[self.orb.lease_id] = clients.Lease(
            self.orb.lease_id, 'ERROR', self.orb.reservation_id, 'error')

        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

        self.assertEqual([], self.heat.created)

    def test_unreachable_blazar_is_retried_until_the_timeout(self):
        get_lease = self.blazar.get_lease
        failures = []

        def flaky(lease_id):
            if len(failures) < 2:
                failures.append(lease_id)
                raise clients.Unavailable('reservation', 'down')
            self.blazar.activate(lease_id)
            return get_lease(lease_id)
        self.blazar.get_lease = flaky

        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

        self.assertEqual(Status.BUILDING, self.stored().status)

    def test_orb_deleted_while_waiting_gets_no_stack(self):
        self.blazar.activate(self.orb.lease_id)
        self.repository.update(self.orb.id, Status.RESERVING,
                               status=Status.DELETING)

        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

        self.assertEqual([], self.heat.created)

    def test_stack_is_removed_if_the_orb_changed_while_it_was_created(self):
        self.blazar.activate(self.orb.lease_id)
        create_stack = self.heat.create_stack

        def racing_delete(*args):
            self.repository.update(self.orb.id, Status.RESERVING,
                                   status=Status.DELETING)
            return create_stack(*args)
        self.heat.create_stack = racing_delete

        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

        self.assertEqual({}, self.heat.stacks)
        self.assertEqual(Status.DELETING, self.stored().status)

    def test_refused_stack_puts_the_orb_in_error_with_heat_reason(self):
        self.blazar.activate(self.orb.lease_id)
        self.heat.refuse_with = clients.Rejected(
            'Quota exceeded for ports', 400)

        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

        self.assertEqual(Status.ERROR, self.stored().status)
        self.assertEqual('Quota exceeded for ports', self.stored().fault)

    def test_unexpected_failure_is_recorded_inside_the_thread(self):
        def broken(lease_id):
            raise RuntimeError('bug')
        self.blazar.get_lease = broken

        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

        self.assertEqual(Status.ERROR, self.stored().status)
        self.assertEqual('creation interrupted by an internal error',
                         self.stored().fault)

    def test_lease_read_refused_is_recorded_with_its_reason(self):
        def refused(lease_id):
            raise clients.Rejected('The request you have made requires '
                                   'authentication.', 401)
        self.blazar.get_lease = refused

        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

        self.assertEqual(Status.ERROR, self.stored().status)
        self.assertIn('requires authentication', self.stored().fault)


class TestTemplate(unittest.TestCase):

    def setUp(self):
        conf.CONF([], project='orbit', default_config_files=[])
        self.addCleanup(conf.CONF.reset)

    def test_creator_sends_exactly_the_parameters_the_template_needs(self):
        parameters = yaml.safe_load(creation.load_template())['parameters']
        required = {name for name, spec in parameters.items()
                    if 'default' not in spec}

        sent = set(creation.Creator._parameters(fakes.orb(), 'key'))

        self.assertLessEqual(required, sent)
        self.assertLessEqual(sent, set(parameters))

    def test_machine_is_reachable_only_through_its_own_router(self):
        resources = yaml.safe_load(creation.load_template())['resources']

        port = resources['port']['properties']
        self.assertEqual({'get_resource': 'network'}, port['network'])
        self.assertEqual([{'subnet': {'get_resource': 'subnet'}}],
                         port['fixed_ips'])
        self.assertEqual(
            {'router': {'get_resource': 'router'},
             'subnet': {'get_resource': 'subnet'}},
            resources['router_interface']['properties'])
        # Neutron associates the external address only with a port reachable
        # from the router.
        self.assertEqual('router_interface',
                         resources['floating_ip_association']['depends_on'])
