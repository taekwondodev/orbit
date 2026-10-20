"""Le operazioni sugli orb, indipendenti da HTTP."""

import dataclasses
import uuid

from orbit.conf import CONF
from orbit import orb as orb_model

Status = orb_model.Status


@dataclasses.dataclass(frozen=True)
class Context:
    """Chi fa la richiesta, e la sua autenticazione per agire a suo nome."""
    project_id: str
    user_id: str
    auth: object


@dataclasses.dataclass(frozen=True)
class CreateRequest:
    size: orb_model.Size
    public_key: str
    image: str


@dataclasses.dataclass(frozen=True)
class Observed:
    """Un orb come appare adesso, con l'indirizzo se e raggiungibile."""
    orb: orb_model.Orb
    ssh_host: str | None = None


class Orbs:

    def __init__(self, repository, clients_for):
        self._repository = repository
        self._clients_for = clients_for

    def create(self, context, request):
        """Prenota la capacita e registra l'orb in RESERVING.

        Se Blazar rifiuta la prenotazione non resta nulla: ne lease ne riga.
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
        return Observed(orb)

    def get(self, context, orb_id):
        """L'orb, o None se non esiste nel progetto di chi chiede."""
        orb = self._repository.get(context.project_id, orb_id)
        return Observed(orb) if orb else None

    def list(self, context, status=None):
        return [Observed(orb)
                for orb in self._repository.list(context.project_id, status)]
