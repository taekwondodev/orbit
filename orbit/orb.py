"""The orb as the service stores it. See docs/design/state.md."""

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
    ssh_allowed_cidr: str | None = None
    # Read once from the console at boot: see docs/adr/0007.
    ssh_host_keys: tuple[str, ...] | None = None
    updated_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None

    @property
    def resource_name(self):
        """Name of lease and stack: finds the resources even without the table."""
        return f'orbit-{self.id}'


def utcnow():
    """UTC time without time zone, as the database stores it."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
