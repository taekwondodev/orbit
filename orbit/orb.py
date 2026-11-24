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
    lease_id: str
    reservation_id: str
    status: Status
    created_at: datetime.datetime
    stack_id: str | None = None
    fault: str | None = None
    ssh_allowed_cidr: str | None = None
    ssh_host_keys: tuple[str, ...] | None = None
    updated_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None

    @property
    def resource_name(self):
        # Deterministic, so the resources are found even without the table.
        return f'orbit-{self.id}'


def utcnow():
    # The database stores naive datetimes.
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
