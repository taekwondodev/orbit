"""One test per row of the reconciliation table in state.md."""

import datetime
import unittest

from orbit import clients
from orbit import lifecycle
from orbit import orb as orb_model
from orbit.tests.unit import fakes

Status = orb_model.Status
CREATED = datetime.datetime(2026, 10, 20, 12, 0, 0)
TIMEOUT = 120

PENDING = clients.Lease('lease-1', 'PENDING', 'reservation-1', 'pending')
ACTIVE_LEASE = clients.Lease('lease-1', 'ACTIVE', 'reservation-1', 'active')
FAILED_LEASE = clients.Lease('lease-1', 'ERROR', 'reservation-1', 'error')
RUNNING = clients.Server('server-1', 'ACTIVE')


def stack(status, reason='', **outputs):
    return clients.Stack('stack-1', status, reason, outputs)


COMPLETE = stack('CREATE_COMPLETE', ssh_host='172.24.4.17',
                 server_id='server-1')


def observe(lease=ACTIVE_LEASE, stack=None, server=None, after=10,
            **orb_fields):
    orb = fakes.orb(created_at=CREATED, **orb_fields)
    now = CREATED + datetime.timedelta(seconds=after)
    return lifecycle.observe(orb, now, TIMEOUT, lease, stack, server)


def result(status, fault=None, ssh_host=None):
    return lifecycle.Observation(status, fault, ssh_host)


class TestObserve(unittest.TestCase):

    def test_lease_waiting_for_activation_is_reserving(self):
        self.assertEqual(result(Status.RESERVING), observe(lease=PENDING))

    def test_no_stack_within_the_wait_limit_is_reserving(self):
        self.assertEqual(result(Status.RESERVING), observe(after=119))

    def test_no_stack_past_the_wait_limit_is_interrupted(self):
        self.assertEqual(result(Status.ERROR, lifecycle.INTERRUPTED),
                         observe(after=120))

    def test_failed_lease_is_error(self):
        observed = observe(lease=FAILED_LEASE, stack_id='stack-1',
                           status=Status.ACTIVE, stack=COMPLETE,
                           server=RUNNING)

        self.assertEqual(Status.ERROR, observed.status)
        self.assertIn('ERROR', observed.fault)

    def test_stack_in_progress_is_building(self):
        self.assertEqual(result(Status.BUILDING), observe(
            stack_id='stack-1', status=Status.BUILDING,
            stack=stack('CREATE_IN_PROGRESS')))

    def test_complete_stack_with_running_server_is_active_with_address(self):
        self.assertEqual(result(Status.ACTIVE, ssh_host='172.24.4.17'),
                         observe(stack_id='stack-1', status=Status.BUILDING,
                                 stack=COMPLETE, server=RUNNING))

    def test_failed_stack_is_error_with_heat_reason(self):
        self.assertEqual(
            result(Status.ERROR, 'Quota exceeded for instances'),
            observe(stack_id='stack-1', status=Status.BUILDING,
                    stack=stack('CREATE_FAILED',
                                'Quota exceeded for instances')))

    def test_complete_stack_without_its_server_is_error(self):
        for server in (None, clients.Server('server-1', 'SHUTOFF')):
            with self.subTest(server=server):
                self.assertEqual(
                    result(Status.ERROR, lifecycle.SERVER_GONE),
                    observe(stack_id='stack-1', status=Status.ACTIVE,
                            stack=COMPLETE, server=server))

    def test_missing_lease_outside_deletion_is_error(self):
        self.assertEqual(result(Status.ERROR, lifecycle.LEASE_GONE),
                         observe(lease=None, stack_id='stack-1',
                                 status=Status.ACTIVE, stack=COMPLETE,
                                 server=RUNNING))

    def test_missing_stack_after_creation_outside_deletion_is_error(self):
        self.assertEqual(result(Status.ERROR, lifecycle.STACK_GONE),
                         observe(stack_id='stack-1', status=Status.ACTIVE,
                                 stack=None))

    def test_deleting_with_stack_or_lease_left_is_deleting(self):
        for lease, remaining in ((ACTIVE_LEASE, None),
                                 (None, stack('DELETE_IN_PROGRESS'))):
            with self.subTest(lease=lease, stack=remaining):
                self.assertEqual(result(Status.DELETING),
                                 observe(lease=lease, stack=remaining,
                                         status=Status.DELETING))

    def test_deleting_with_nothing_left_is_deleted(self):
        self.assertEqual(result(Status.DELETED),
                         observe(lease=None, status=Status.DELETING))

    def test_failed_stack_deletion_is_error_with_heat_reason(self):
        self.assertEqual(
            result(Status.ERROR, 'Port in use'),
            observe(status=Status.DELETING,
                    stack=stack('DELETE_FAILED', 'Port in use')))

    def test_deleted_stays_deleted(self):
        self.assertEqual(result(Status.DELETED),
                         observe(lease=None, status=Status.DELETED))


class TestObserveError(unittest.TestCase):

    def test_error_keeps_its_first_cause(self):
        self.assertEqual(
            result(Status.ERROR, 'Quota exceeded for instances'),
            observe(stack_id='stack-1', status=Status.ERROR,
                    fault='Quota exceeded for instances', stack=None))

    def test_refused_stack_stays_error_without_a_stack(self):
        self.assertEqual(result(Status.ERROR, 'Invalid image'),
                         observe(status=Status.ERROR, fault='Invalid image',
                                 after=1))

    def test_error_ends_when_reality_recovers(self):
        self.assertEqual(result(Status.ACTIVE, ssh_host='172.24.4.17'),
                         observe(stack_id='stack-1', status=Status.ERROR,
                                 fault=lifecycle.SERVER_GONE,
                                 stack=COMPLETE, server=RUNNING))
