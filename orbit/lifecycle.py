"""The status of an orb derived from what Blazar, Heat and Nova show.

Translates the reconciliation table of docs/design/state.md: if reality and
the orbs table diverge, reality is right.
"""

import dataclasses

from orbit import orb as orb_model

Status = orb_model.Status

INTERRUPTED = 'creation interrupted'
LEASE_GONE = 'reservation no longer present'
STACK_GONE = 'stack no longer present'
SERVER_GONE = 'machine no longer available'
HOST_KEYS_MISSING = 'SSH host keys not published on the console'


@dataclasses.dataclass(frozen=True)
class Observation:
    status: Status
    fault: str | None = None
    ssh_host: str | None = None
    ssh_host_keys: tuple[str, ...] | None = None


@dataclasses.dataclass(frozen=True)
class Timeouts:
    """Seconds from the creation request within which the stack must exist
    (``creation``) and the machine must publish its host keys (``ready``)."""
    creation: int
    ready: int


def awaits_host_keys(orb, now, timeouts):
    """Whether the machine's console may still be read for its host keys.

    Only within ``ready_timeout`` of the creation request: a block printed
    later may come from a process inside the orb, not from the boot
    (docs/adr/0007).
    """
    return (orb.ssh_host_keys is None
            and orb.status not in (Status.DELETING, Status.DELETED)
            and _age(orb, now) < timeouts.ready)


def observe(orb, now, timeouts, lease, stack, server, ssh_host_keys):
    """The status of ``orb`` given the observed lease, stack and machine.

    ``lease``, ``stack`` and ``server`` are None when the resource does not
    exist. The stack counts only if the orb has recorded one or is being
    deleted; the machine only if the stack is complete. ``ssh_host_keys``
    are the machine's host keys, stored or just read from its console, or
    None if not published yet: without them the orb is not ACTIVE.
    """
    observation = _observe(orb, now, timeouts, lease, stack, server,
                           ssh_host_keys)
    if observation.status is Status.ERROR and orb.status is Status.ERROR:
        # The first reason is the useful one: the failed stack might already
        # have been deleted when someone reads the orb again.
        return Observation(Status.ERROR, orb.fault or observation.fault)
    return observation


def _observe(orb, now, timeouts, lease, stack, server, ssh_host_keys):
    if orb.status is Status.DELETED:
        return Observation(Status.DELETED)
    if orb.status is Status.DELETING:
        if stack is not None and stack.status == 'DELETE_FAILED':
            return Observation(Status.ERROR, stack.status_reason)
        if stack is not None or lease is not None:
            return Observation(Status.DELETING)
        return Observation(Status.DELETED)

    if lease is None:
        return Observation(Status.ERROR, LEASE_GONE)
    if lease.is_failed:
        return Observation(
            Status.ERROR, f'reservation in error: lease {lease.status}, '
                          f'reservation {lease.reservation_status}')

    if orb.stack_id is None:
        if orb.status is Status.ERROR:
            return Observation(Status.ERROR, orb.fault)
        if _age(orb, now) < timeouts.creation:
            return Observation(Status.RESERVING)
        return Observation(Status.ERROR, INTERRUPTED)

    if stack is None:
        return Observation(Status.ERROR, STACK_GONE)
    if stack.status == 'CREATE_IN_PROGRESS':
        return Observation(Status.BUILDING)
    if stack.status == 'CREATE_COMPLETE':
        if server is None or server.status != 'ACTIVE':
            return Observation(Status.ERROR, SERVER_GONE)
        if ssh_host_keys is None:
            # The machine is up but sshd may not be: the keys appear on the
            # console once the client's key is installed.
            if _age(orb, now) < timeouts.ready:
                return Observation(Status.BUILDING)
            return Observation(Status.ERROR, HOST_KEYS_MISSING)
        return Observation(Status.ACTIVE,
                           ssh_host=stack.outputs.get('ssh_host'),
                           ssh_host_keys=ssh_host_keys)
    if stack.status in ('CREATE_FAILED', 'DELETE_FAILED'):
        return Observation(Status.ERROR, stack.status_reason)
    return Observation(Status.ERROR, f'stack in status {stack.status}')


def _age(orb, now):
    return (now - orb.created_at).total_seconds()
