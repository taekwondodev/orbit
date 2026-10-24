from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from horizon import exceptions
from horizon import tables
from horizon import views
from horizon.utils import memoized

from orbit.dashboard import client
from orbit.dashboard.orbs import tables as orbs_tables


class IndexView(tables.DataTableView):
    table_class = orbs_tables.OrbsTable
    page_title = _('Orbs')

    def get_data(self):
        try:
            orbs = client.orb_list(self.request)
        except Exception:
            self.get_table().unavailable = True
            exceptions.handle(self.request, _('Unable to retrieve orbs.'))
            return []
        # Deleted orbs hold no resources; their history stays in
        # `openstack orb list --status DELETED`.
        return [orb for orb in orbs if orb.status != 'DELETED']


class DetailView(views.HorizonTemplateView):
    template_name = 'project/orbs/detail.html'
    page_title = _('Orb Details')

    @memoized.memoized_method
    def _get_data(self):
        try:
            return client.orb_get(self.request, self.kwargs['orb_id'])
        except Exception:
            exceptions.handle(
                self.request,
                _('Unable to retrieve details for orb "%s".')
                % self.kwargs['orb_id'],
                redirect=reverse('horizon:project:orbs:index'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orb = self._get_data()
        context['orb'] = orb
        context['status_label'] = dict(
            orbs_tables.STATUS_DISPLAY_CHOICES).get(orb.status, orb.status)
        return context
