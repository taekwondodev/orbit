from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from horizon import tables
from horizon.utils import filters

from orbit.dashboard.orbs import overview

CREATE_REQUEST = 'POST /v1/orbs'

STATUS_DISPLAY_CHOICES = (
    ('RESERVING', pgettext_lazy('Current status of an orb', 'Reserving')),
    ('BUILDING', pgettext_lazy('Current status of an orb', 'Building')),
    ('ACTIVE', pgettext_lazy('Current status of an orb', 'Active')),
    ('ERROR', pgettext_lazy('Current status of an orb', 'Error')),
    ('DELETING', pgettext_lazy('Current status of an orb', 'Deleting')),
    ('DELETED', pgettext_lazy('Current status of an orb', 'Deleted')),
)

STEPS = ('RESERVING', 'BUILDING', 'ACTIVE')

IN_PROGRESS = ('RESERVING', 'BUILDING', 'DELETING')


def status_label(status):
    return dict(STATUS_DISPLAY_CHOICES).get(status, status)


def step_states(status):
    if status not in STEPS:
        return None
    reached = STEPS.index(status)
    return [
        'done'
        if index < reached or status == 'ACTIVE'
        else 'now'
        if index == reached
        else 'todo'
        for index in range(len(STEPS))
    ]


def status_badge(status):
    classes = f'orbit-badge orbit-{overview.group_of(status) or "deleted"}'
    if status in IN_PROGRESS:
        classes += ' orbit-pulse'
    return format_html(
        '<span class="{}"><span class="orbit-dot"></span>{}</span>',
        classes,
        status_label(status),
    )


def get_status(orb):
    states = step_states(orb.status)
    if states is None:
        return status_badge(orb.status)
    bars = format_html_join(
        '', '<i class="orbit-step-{}"></i>', ((state,) for state in states)
    )
    return format_html(
        '{}<span class="orbit-steps" aria-hidden="true">{}</span>',
        status_badge(orb.status),
        bars,
    )


def get_id(orb):
    link = format_html(
        '<a class="orbit-id" href="{}">{}</a>',
        reverse('horizon:project:orbs:detail', args=[orb.id]),
        orb.id,
    )
    if not orb.fault:
        return link
    return format_html(
        '{}<span class="orbit-fault">{}</span>', link, orb.fault
    )


def get_size(orb):
    return format_html(
        '<span class="orbit-chip"><b>{}</b> vCPU</span>'
        '<span class="orbit-chip"><b>{}</b> MiB</span>'
        '<span class="orbit-chip"><b>{}</b> GiB</span>',
        orb.size['vcpus'],
        orb.size['memory_mb'],
        orb.size['disk_gb'],
    )


class OrbRow(tables.Row):
    def load_cells(self, datum=None):
        super().load_cells(datum)
        orb = self.datum
        assert orb is not None, 'Horizon loads cells only with a datum'
        self.attrs['data-orbit-status'] = orb.status
        if orb.status == 'ERROR':
            self.classes.append('orbit-row-error')


class OrbsTable(tables.DataTable):
    status = tables.Column(
        get_status, verbose_name=_('Status'), classes=('orbit-status-cell',)
    )
    id = tables.Column(get_id, verbose_name=_('ID'))
    size = tables.Column(get_size, verbose_name=_('Size'))
    age = tables.Column(
        'created_at',
        verbose_name=_('Age'),
        filters=(filters.parse_isotime, filters.timesince_sortable),
        attrs={'data-type': 'timesince'},
    )

    unavailable = False

    def get_empty_message(self):
        if self.unavailable:
            return super().get_empty_message()
        return format_html(
            '{} <code>{}</code>',
            _('No orbs in this project. Create one through the orbit API:'),
            CREATE_REQUEST,
        )

    class Meta:
        name = 'orbs'
        verbose_name = _('Orbs')
        row_class = OrbRow
        table_actions = (tables.FilterAction,)
