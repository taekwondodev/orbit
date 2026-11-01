"""The reconciliation: the status of an orb re-read from Blazar, Heat and
Nova and written back to the table.

Run by every read of an orb and by the creation task while it follows a new
orb (docs/design/state.md, Reconciliation).
"""

import dataclasses

from oslo_log import log

from orbit import clients as orbit_clients
from orbit.conf import CONF
from orbit import lifecycle
from orbit import orb as orb_model
from orbit import ssh

LOG = log.getLogger(__name__)
Status = orb_model.Status


@dataclasses.dataclass(frozen=True)
class Observed:
    """An orb as it looks now, with the address if it is reachable."""
    orb: orb_model.Orb
    ssh_host: str | None = None


def reconcile(repository, orb, clients, now):
    """Re-read lease, stack and machine at ``now``, and correct the table."""
    if orb.status is Status.DELETED:
        return Observed(orb)
    lease = clients.blazar.get_lease(orb.lease_id)
    stack = None
    if orb.stack_id is not None or orb.status is Status.DELETING:
        stack = clients.heat.get_stack(orb.resource_name)
    server = None
    if stack is not None and stack.status == 'CREATE_COMPLETE':
        server_id = stack.outputs.get('server_id')
        server = clients.nova.get_server(server_id) if server_id else None

    timeouts = lifecycle.Timeouts(creation=CONF.orbs.creation_timeout,
                                  ready=CONF.orbs.ready_timeout)
    ssh_host_keys = orb.ssh_host_keys
    if lifecycle.awaits_host_keys(orb, now, timeouts):
        ssh_host_keys = _read_host_keys(orb, clients.nova, server)

    observation = lifecycle.observe(orb, now, timeouts, lease, stack,
                                    server, ssh_host_keys)
    changes = {}
    if (observation.status, observation.fault) != (orb.status, orb.fault):
        changes.update(status=observation.status, fault=observation.fault)
    if orb.ssh_host_keys is None and observation.ssh_host_keys:
        # Stored once: the console may lose them or show forged ones
        # later (docs/adr/0007).
        changes.update(ssh_host_keys=observation.ssh_host_keys)
    if not changes:
        return Observed(orb, observation.ssh_host)
    if not repository.update(orb.id, orb.status, **changes):
        # Another request, or the creation task, wrote first: its
        # version wins, and is checked again on the next read.
        return Observed(repository.get(orb.project_id, orb.id))
    return Observed(repository.get(orb.project_id, orb.id),
                    observation.ssh_host)


def _read_host_keys(orb, nova, server):
    """The host keys on the running machine's console, or None.

    A console that cannot be read counts as keys not published yet: the
    read of the orb does not fail for it, and past ready_timeout the orb
    goes to ERROR.
    """
    if server is None or server.status != 'ACTIVE':
        return None
    try:
        console = nova.get_console_output(server.id)
    except (orbit_clients.Rejected, orbit_clients.Unavailable) as e:
        LOG.warning('Console of %s not readable: %s',
                    orb.resource_name, e)
        return None
    return ssh.host_keys(console)
