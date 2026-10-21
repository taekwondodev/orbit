"""Lo stato di un orb ricavato da cio che Blazar, Heat e Nova mostrano.

Traduce la tabella di riallineamento di docs/design/state.md: se la realta e
la tabella orbs divergono, ha ragione la realta.
"""

import dataclasses

from orbit import orb as orb_model

Status = orb_model.Status

INTERRUPTED = 'creazione interrotta'
LEASE_GONE = 'prenotazione non più presente'
STACK_GONE = 'stack non più presente'
SERVER_GONE = 'macchina non più disponibile'


@dataclasses.dataclass(frozen=True)
class Observation:
    status: Status
    fault: str | None = None
    ssh_host: str | None = None


def observe(orb, now, creation_timeout, lease, stack, server):
    """Lo stato di ``orb`` dati lease, stack e macchina osservati.

    ``lease``, ``stack`` e ``server`` valgono None quando la risorsa non
    esiste. Lo stack conta solo se l'orb ne ha registrato uno o e in
    cancellazione; la macchina solo se lo stack e completo.
    """
    observation = _observe(orb, now, creation_timeout, lease, stack, server)
    if observation.status is Status.ERROR and orb.status is Status.ERROR:
        # Il primo motivo e quello utile: lo stack fallito potrebbe essere
        # gia stato cancellato quando qualcuno rilegge l'orb.
        return Observation(Status.ERROR, orb.fault or observation.fault)
    return observation


def _observe(orb, now, creation_timeout, lease, stack, server):
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
            Status.ERROR, f'prenotazione in errore: lease {lease.status}, '
                          f'prenotazione {lease.reservation_status}')

    if orb.stack_id is None:
        if orb.status is Status.ERROR:
            return Observation(Status.ERROR, orb.fault)
        if (now - orb.created_at).total_seconds() < creation_timeout:
            return Observation(Status.RESERVING)
        return Observation(Status.ERROR, INTERRUPTED)

    if stack is None:
        return Observation(Status.ERROR, STACK_GONE)
    if stack.status == 'CREATE_IN_PROGRESS':
        return Observation(Status.BUILDING)
    if stack.status == 'CREATE_COMPLETE':
        if server is None or server.status != 'ACTIVE':
            return Observation(Status.ERROR, SERVER_GONE)
        return Observation(Status.ACTIVE,
                           ssh_host=stack.outputs.get('ssh_host'))
    if stack.status in ('CREATE_FAILED', 'DELETE_FAILED'):
        return Observation(Status.ERROR, stack.status_reason)
    return Observation(Status.ERROR, f'stack in stato {stack.status}')
