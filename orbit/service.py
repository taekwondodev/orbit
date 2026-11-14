"""The operations on orbs, independent of HTTP."""

import dataclasses
import uuid

from orbit.conf import CONF
from orbit import orb as orb_model
from orbit import reconciliation

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
    ssh_allowed_cidr: str


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
        return reconciliation.Observed(orb)

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
        return reconciliation.Observed(self._repository.get(context.project_id, orb_id))

    def _observe(self, orb, clients):
        return reconciliation.reconcile(self._repository, orb, clients,
                                        orb_model.utcnow())

