"""The summary above the Orbs table, computed from one list read.

Only what `GET /v1/orbs` returns: statuses, sizes and creation times,
deleted history included. orbit does not report what a client does inside
an orb, so neither does the summary.
"""

import dataclasses
import datetime

from django.utils import timezone
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _
from horizon.utils import filters

# Statuses that hold capacity: every orb until it is DELETED.
HOLDING = ('RESERVING', 'BUILDING', 'ACTIVE', 'ERROR', 'DELETING')

GROUPS = (
    ('active', _('Active'), ('ACTIVE',)),
    ('starting', _('Starting'), ('RESERVING', 'BUILDING')),
    ('error', _('Error'), ('ERROR',)),
    ('deleting', _('Deleting'), ('DELETING',)),
)

ACTIVITY_DAYS = 14


@dataclasses.dataclass(frozen=True)
class Group:
    key: str
    label: str | Promise
    count: int


@dataclasses.dataclass(frozen=True)
class Day:
    date: datetime.date
    count: int
    # Bar height relative to the busiest day of the window.
    percent: int


@dataclasses.dataclass(frozen=True)
class Overview:
    groups: tuple
    vcpus: int
    memory_gib: float
    disk_gb: int
    days: tuple
    created_last_week: int


def group_of(status):
    for key, _label, statuses in GROUPS:
        if status in statuses:
            return key
    return None


def summarize(orbs, today):
    """Summarize every orb of the list, DELETED ones included."""
    holding = [orb for orb in orbs if orb.status in HOLDING]
    groups = tuple(
        Group(key, label, sum(orb.status in statuses for orb in holding))
        for key, label, statuses in GROUPS
    )
    created = [_local_date(orb.created_at) for orb in orbs]
    counts = [
        created.count(today - datetime.timedelta(days=offset))
        for offset in range(ACTIVITY_DAYS - 1, -1, -1)
    ]
    busiest = max(counts) or 1
    days = tuple(
        Day(
            today - datetime.timedelta(days=ACTIVITY_DAYS - 1 - index),
            count,
            round(100 * count / busiest),
        )
        for index, count in enumerate(counts)
    )
    return Overview(
        groups=groups,
        vcpus=sum(orb.size['vcpus'] for orb in holding),
        memory_gib=sum(orb.size['memory_mb'] for orb in holding) / 1024,
        disk_gb=sum(orb.size['disk_gb'] for orb in holding),
        days=days,
        created_last_week=sum(counts[-7:]),
    )


def _local_date(created_at):
    # orbit writes UTC; the bars follow the day of the user's time zone.
    return timezone.localtime(filters.parse_isotime(created_at)).date()
