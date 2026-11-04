import datetime
import unittest

import yaml

from orbit import clients
from orbit import conf
from orbit import creation
from orbit import lifecycle
from orbit import orb as orb_model
from orbit.tests.unit import fakes

Status = orb_model.Status
START = datetime.datetime(2026, 10, 20, 12, 0, 0)


class FakeClock:
    """Time advances only when the task waits; what is scheduled at a time
    happens as soon as the wait reaches it."""

    def __init__(self):
        self.now = START
        self.events = []

    def __call__(self):
        return self.now

    def at(self, seconds, action):
        self.events.append((START + datetime.timedelta(seconds=seconds),
                            action))

    def sleep(self, seconds):
        self.now += datetime.timedelta(seconds=seconds)
        due = [event for event in self.events if event[0] <= self.now]
        for event in sorted(due, key=lambda event: event[0]):
            self.events.remove(event)
            event[1]()


class TestCreator(unittest.TestCase):

    def setUp(self):
        conf.CONF([], project='orbit', default_config_files=[])
        self.addCleanup(conf.CONF.reset)
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
                             created_at=START,
                             ssh_allowed_cidr='203.0.113.0/24')
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
        create_stack = self.heat.create_stack
        created_at = []

        def timed(*args):
            created_at.append(self.clock.now)
            return create_stack(*args)
        self.heat.create_stack = timed

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
                          'ssh_allowed_cidr': '203.0.113.0/24',
                          'egress_rules': [],
                          'user_data': ''}, parameters)
        self.assertEqual(Status.BUILDING, self.stored().status)
        self.assertEqual('stack-1', self.stored().stack_id)
        self.assertEqual([START + datetime.timedelta(seconds=4)], created_at)

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

    def test_stack_receives_the_operators_destinations_and_proxy(self):
        conf.CONF.set_override('egress_destinations', ['udp:10.0.0.2:53'],
                               'orbs')
        conf.CONF.set_override('egress_proxy', '172.24.4.1:4750', 'orbs')
        self.activate_after(polls=1)

        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

        parameters = self.heat.created[0][2]
        self.assertEqual(['10.0.0.2/32', '172.24.4.1/32'],
                         [rule['remote_ip_prefix']
                          for rule in parameters['egress_rules']])
        self.assertIn('https_proxy=http://172.24.4.1:4750',
                      parameters['user_data'])

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


class TestFollow(unittest.TestCase):
    """After creating the stack the task follows the orb, without reads."""

    def setUp(self):
        conf.CONF([], project='orbit', default_config_files=[])
        self.addCleanup(conf.CONF.reset)
        self.clients = fakes.fake_clients()
        self.blazar, self.heat = self.clients.blazar, self.clients.heat
        self.nova = self.clients.nova
        self.repository = fakes.repository()
        self.clock = FakeClock()
        self.creator = creation.Creator(self.repository, 'template-text',
                                        sleep=self.clock.sleep,
                                        clock=self.clock)
        lease = self.blazar.create_lease('orbit-x', None, None)
        self.blazar.activate(lease.id)
        self.orb = fakes.orb(lease_id=lease.id,
                             reservation_id=lease.reservation_id,
                             created_at=START)
        self.repository.add(self.orb)

    def stored(self):
        return self.repository.get(self.orb.project_id, self.orb.id)

    def elapsed(self):
        return (self.clock.now - START).total_seconds()

    def machine_up_at(self, seconds):
        def up():
            self.heat.set_status(self.orb.resource_name, 'CREATE_COMPLETE',
                                 ssh_host='172.24.4.17',
                                 server_id='server-1')
            self.nova.servers['server-1'] = clients.Server('server-1',
                                                           'ACTIVE')
        self.clock.at(seconds, up)

    def keys_on_console_at(self, seconds):
        def printed():
            self.nova.consoles['server-1'] = fakes.CONSOLE
        self.clock.at(seconds, printed)

    def run_creation(self):
        self.creator.run(self.orb, self.clients, fakes.PUBLIC_KEY)

    def test_orb_becomes_active_with_its_keys_without_any_read(self):
        self.machine_up_at(30)
        self.keys_on_console_at(200)

        self.run_creation()

        self.assertEqual(Status.ACTIVE, self.stored().status)
        self.assertEqual((fakes.HOST_KEY_ECDSA, fakes.HOST_KEY_ED25519),
                         self.stored().ssh_host_keys)
        self.assertEqual(200, self.elapsed())

    def test_machine_without_keys_goes_to_error_at_ready_timeout(self):
        self.machine_up_at(30)

        self.run_creation()

        self.assertEqual(Status.ERROR, self.stored().status)
        self.assertEqual(lifecycle.HOST_KEYS_MISSING, self.stored().fault)
        self.assertEqual(600, self.elapsed())

    def test_orb_deleted_while_followed_stays_deleting(self):
        self.machine_up_at(30)
        self.clock.at(40, lambda: self.repository.update(
            self.orb.id, Status.BUILDING, status=Status.DELETING))

        self.run_creation()

        self.assertEqual(Status.DELETING, self.stored().status)
        self.assertEqual(40, self.elapsed())

    def test_failed_stack_ends_the_orb_in_error_with_heat_reason(self):
        self.clock.at(10, lambda: self.heat.set_status(
            self.orb.resource_name, 'CREATE_FAILED',
            'Resource CREATE failed: port quota'))

        self.run_creation()

        self.assertEqual(Status.ERROR, self.stored().status)
        self.assertEqual('Resource CREATE failed: port quota',
                         self.stored().fault)
        self.assertEqual(10, self.elapsed())

    def test_refused_token_stops_following_and_leaves_the_status(self):
        def expired(lease_id):
            raise clients.Rejected('The request you have made requires '
                                   'authentication.', 401)
        self.clock.at(10, lambda: setattr(self.blazar, 'get_lease', expired))

        self.run_creation()

        self.assertEqual(Status.BUILDING, self.stored().status)
        self.assertEqual(10, self.elapsed())

    def test_unreachable_heat_is_retried_until_the_orb_is_active(self):
        get_stack = self.heat.get_stack

        def down(name):
            raise clients.Unavailable('orchestration', 'down')
        self.clock.at(10, lambda: setattr(self.heat, 'get_stack', down))
        self.clock.at(20, lambda: setattr(self.heat, 'get_stack', get_stack))
        self.machine_up_at(30)
        self.keys_on_console_at(30)

        self.run_creation()

        self.assertEqual(Status.ACTIVE, self.stored().status)
        self.assertEqual(30, self.elapsed())


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

    def test_outbound_traffic_is_denied_unless_listed(self):
        resources = yaml.safe_load(creation.load_template())['resources']

        rules = resources['security_group']['properties']['rules']
        fixed, listed = rules['list_concat']
        self.assertEqual({'get_param': 'egress_rules'}, listed)
        # Heat keeps Neutron's allow-all egress rules unless the group
        # declares one: the template always does, towards loopback, and
        # towards the network's own DHCP service, without which the machine
        # gets no address.
        egress_rules = [rule for rule in fixed
                        if rule.get('direction') == 'egress']
        self.assertEqual(['127.0.0.1/32', '255.255.255.255/32',
                          {'get_param': 'cidr'}],
                         [rule['remote_ip_prefix'] for rule in egress_rules])
        self.assertEqual([67, 67],
                         [rule['port_range_min'] for rule in egress_rules
                          if rule['protocol'] == 'udp'])
        # Without egress the machine cannot reach the metadata service.
        server = resources['server']['properties']
        self.assertIs(True, server['config_drive'])
        self.assertEqual({'get_param': 'user_data'}, server['user_data'])

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
