"""L'orb come lo conserva il servizio. Vedi docs/design/state.md."""

import dataclasses
import datetime
import enum


class Status(str, enum.Enum):
    RESERVING = 'RESERVING'
    BUILDING = 'BUILDING'
    ACTIVE = 'ACTIVE'
    ERROR = 'ERROR'
    DELETING = 'DELETING'
    DELETED = 'DELETED'


@dataclasses.dataclass(frozen=True)
class Size:
    vcpus: int
    memory_mb: int
    disk_gb: int


@dataclasses.dataclass(frozen=True)
class Orb:
    id: str
    project_id: str
    user_id: str
    size: Size
    image: str
    lease_id: str
    reservation_id: str
    status: Status
    created_at: datetime.datetime
    stack_id: str | None = None
    fault: str | None = None
    updated_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None

    @property
    def resource_name(self):
        """Nome di lease e stack: ritrova le risorse anche senza la tabella."""
        return f'orbit-{self.id}'


def utcnow():
    """Ora UTC senza fuso, come la conserva il database."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
