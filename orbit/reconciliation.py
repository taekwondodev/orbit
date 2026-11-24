import dataclasses

from oslo_log import log

from orbit import clients as orbit_clients
from orbit import lifecycle, ssh
from orbit import orb as orb_model
from orbit.conf import CONF

LOG = log.getLogger(__name__)
Status = orb_model.Status


@dataclasses.dataclass(frozen=True)
class Observed:
    orb: orb_model.Orb
    ssh_host: str | None = None


def reconcile(repository, orb, clients, now):
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

    timeouts = lifecycle.Timeouts(
        creation=CONF.orbs.creation_timeout, ready=CONF.orbs.ready_timeout
    )
    ssh_host_keys = orb.ssh_host_keys
    if lifecycle.awaits_host_keys(orb, now, timeouts):
        ssh_host_keys = _read_host_keys(orb, clients.nova, server)

    observation = lifecycle.observe(
        orb, now, timeouts, lease, stack, server, ssh_host_keys
    )
    changes = {}
    if (observation.status, observation.fault) != (orb.status, orb.fault):
        changes.update(status=observation.status, fault=observation.fault)
    if orb.ssh_host_keys is None and observation.ssh_host_keys:
        changes.update(ssh_host_keys=observation.ssh_host_keys)
    if not changes:
        return Observed(orb, observation.ssh_host)
    if not repository.update(orb.id, orb.status, **changes):
        # Another request, or the creation task, wrote first: its
        # version wins, and is checked again now, so that an orb it
        # made ACTIVE comes back with its address.
        return reconcile(
            repository, repository.get(orb.project_id, orb.id), clients, now
        )
    return Observed(
        repository.get(orb.project_id, orb.id), observation.ssh_host
    )


def _read_host_keys(orb, nova, server):
    # An unreadable console counts as keys not published yet: the read of the
    # orb does not fail for it, and past ready_timeout the orb goes to ERROR.
    if server is None or server.status != 'ACTIVE':
        return None
    try:
        console = nova.get_console_output(server.id)
    except (orbit_clients.Rejected, orbit_clients.Unavailable) as e:
        LOG.warning('Console of %s not readable: %s', orb.resource_name, e)
        return None
    return ssh.host_keys(console)
