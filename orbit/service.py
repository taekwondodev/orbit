"""The operations on orbs, independent of HTTP."""

import dataclasses
import uuid

from oslo_log import log

from orbit import clients as orbit_clients
from orbit.conf import CONF
from orbit import lifecycle
from orbit import orb as orb_model
from orbit import ssh

LOG = log.getLogger(__name__)
Status = orb_model.Status


@dataclasses.dataclass(frozen=True)
class Context:
    """Who makes the request, and their authentication to act for them."""
    project_id: str
    user_id: str
    auth: object


@dataclasses.dataclass(frozen=True)
class CreateRequest:
    size: orb_model.Size
    public_key: str
    image: str
    ssh_allowed_cidr: str


@dataclasses.dataclass(frozen=True)
class Observed:
    """An orb as it looks now, with the address if it is reachable."""
    orb: orb_model.Orb
    ssh_host: str | None = None


class Orbs:

    def __init__(self, repository, clients_for, creator):
        self._repository = repository
        self._clients_for = clients_for
        self._creator = creator

    def create(self, context, request):
        """Reserve the capacity, record the orb in RESERVING and start the
        creation, which goes on after the response.

        If Blazar rejects the reservation nothing is left: no lease, no row.
        """
        clients = self._clients_for(context.auth)
        orb_id = str(uuid.uuid4())
        lease = clients.blazar.create_lease(
            f'orbit-{orb_id}', request.size, CONF.orbs.lease_end_date)
        orb = orb_model.Orb(
            id=orb_id,
            project_id=context.project_id,
            user_id=context.user_id,
            size=request.size,
            image=request.image,
            ssh_allowed_cidr=request.ssh_allowed_cidr,
            lease_id=lease.id,
            reservation_id=lease.reservation_id,
            status=Status.RESERVING,
            created_at=orb_model.utcnow(),
        )
        try:
            self._repository.add(orb)
        except Exception:
            clients.blazar.delete_lease(lease.id)
            raise
        self._creator.start(orb, clients, request.public_key)
        return Observed(orb)

    def get(self, context, orb_id):
        """The orb as it looks now, or None if not in the project."""
        orb = self._repository.get(context.project_id, orb_id)
        if orb is None:
            return None
        return self._observe(orb, self._clients_for(context.auth))

    def list(self, context, status=None):
        clients = self._clients_for(context.auth)
        observed = [self._observe(orb, clients)
                    for orb in self._repository.list(context.project_id)]
        if status is None:
            return observed
        return [o for o in observed if o.orb.status is status]

    def delete(self, context, orb_id):
        """Delete stack and lease. Repeatable: retries what is left.

        Returns None if the orb does not exist in the project.
        """
        orb = self._repository.get(context.project_id, orb_id)
        if orb is None:
            return None
        while orb.status not in (Status.DELETING, Status.DELETED):
            if self._repository.update(orb.id, orb.status,
                                       status=Status.DELETING, fault=None):
                break
            orb = self._repository.get(context.project_id, orb_id)
        if orb.status is not Status.DELETED:
            clients = self._clients_for(context.auth)
            # First the stack, then the lease: deleting the lease, Blazar
            # destroys the machine anyway; the order serves Heat's cleanup
            # (docs/adr/0005).
            clients.heat.delete_stack(orb.resource_name)
            clients.blazar.delete_lease(orb.lease_id)
        return Observed(self._repository.get(context.project_id, orb_id))

    def _observe(self, orb, clients):
        """Re-read lease, stack and machine, and correct the table."""
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

        now = orb_model.utcnow()
        timeouts = lifecycle.Timeouts(creation=CONF.orbs.creation_timeout,
                                      ready=CONF.orbs.ready_timeout)
        ssh_host_keys = orb.ssh_host_keys
        if lifecycle.awaits_host_keys(orb, now, timeouts):
            ssh_host_keys = self._read_host_keys(orb, clients.nova, server)

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
        if not self._repository.update(orb.id, orb.status, **changes):
            # Another request, or the creation task, wrote first: its
            # version wins, and is checked again on the next read.
            return Observed(self._repository.get(orb.project_id, orb.id))
        return Observed(self._repository.get(orb.project_id, orb.id),
                        observation.ssh_host)

    @staticmethod
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
