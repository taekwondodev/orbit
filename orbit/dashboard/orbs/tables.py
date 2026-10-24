from django import http
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from horizon import tables
from horizon.utils import filters

from orbit.dashboard import client

CREATE_COMMAND = ('openstack orb create --vcpus 1 --memory 512 --disk 1 '
                  '--public-key ~/.ssh/id_ed25519.pub')

STATUS_DISPLAY_CHOICES = (
    ('RESERVING', pgettext_lazy('Current status of an orb', 'Reserving')),
    ('BUILDING', pgettext_lazy('Current status of an orb', 'Building')),
    ('ACTIVE', pgettext_lazy('Current status of an orb', 'Active')),
    ('ERROR', pgettext_lazy('Current status of an orb', 'Error')),
    ('DELETING', pgettext_lazy('Current status of an orb', 'Deleting')),
    ('DELETED', pgettext_lazy('Current status of an orb', 'Deleted')),
)


def get_size(orb):
    # The units of the request, not Horizon's GB: the user reads back the
    # numbers they asked for.
    return _('%(vcpus)s vCPU · %(memory_mb)s MiB · %(disk_gb)s GiB') % orb.size


class UpdateRow(tables.Row):
    ajax = True

    def get_data(self, request, orb_id):
        orb = client.orb_get(request, orb_id)
        if orb.status == 'DELETED':
            # A 404 to the row update removes the row from the table.
            raise http.Http404
        return orb


class OrbsTable(tables.DataTable):
    # None keeps a row refreshing until the orb settles.
    STATUS_CHOICES = (
        ('RESERVING', None),
        ('BUILDING', None),
        ('DELETING', None),
        ('ACTIVE', True),
        ('ERROR', False),
    )

    id = tables.Column('id', verbose_name=_('ID'),
                       link='horizon:project:orbs:detail')
    image = tables.Column('image', verbose_name=_('Image'))
    ssh_host = tables.Column('ssh_host', verbose_name=_('SSH Host'))
    size = tables.Column(get_size, verbose_name=_('Size'))
    status = tables.Column('status', verbose_name=_('Status'), status=True,
                           status_choices=STATUS_CHOICES,
                           display_choices=STATUS_DISPLAY_CHOICES)
    age = tables.Column('created_at', verbose_name=_('Age'),
                        filters=(filters.parse_isotime,
                                 filters.timesince_sortable),
                        attrs={'data-type': 'timesince'})

    # Set by the view when the list could not be read: then "no orbs"
    # would be false.
    unavailable = False

    def get_empty_message(self):
        if self.unavailable:
            return super().get_empty_message()
        # The panel is read-only: without this, an empty list is a dead end.
        return format_html('{} <code>{}</code>',
                           _('No orbs in this project. Create one from the '
                             'command line:'),
                           CREATE_COMMAND)

    class Meta:
        name = 'orbs'
        verbose_name = _('Orbs')
        status_columns = ['status']
        row_class = UpdateRow
        table_actions = (tables.FilterAction,)
