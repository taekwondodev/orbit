from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from horizon import exceptions
from horizon import tables
from horizon import views
from horizon.utils import memoized

from orbit.dashboard import client
from orbit.dashboard.exceptions import OrbitError
from orbit.dashboard.exceptions import OrbitUnauthorized
from orbit.dashboard.exceptions import OrbNotFound
from orbit.dashboard.orbs import tables as orbs_tables


class LiveViewMixin:
    """Use the same authenticated view for page loads and live snapshots."""

    @property
    def live(self):
        return self.request.GET.get('live') == '1'

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except OrbitError as error:
            if not self.live:
                raise
            if isinstance(error, OrbitUnauthorized):
                status = 401
            elif isinstance(error, OrbNotFound):
                status = 404
            else:
                status = 503
            response = JsonResponse({'error': str(error)}, status=status)
            response['Cache-Control'] = 'no-store'
            return response

    def render_to_response(self, context, **response_kwargs):
        if not self.live:
            return super().render_to_response(context, **response_kwargs)
        response = JsonResponse({'html': render_to_string(
            self.fragment_template, context, request=self.request)})
        response['Cache-Control'] = 'no-store'
        return response


class IndexView(LiveViewMixin, tables.DataTableView):
    template_name = 'project/orbs/index.html'
    fragment_template = 'project/orbs/_list.html'
    table_class = orbs_tables.OrbsTable
    page_title = _('Orbs')

    def get_data(self):
        try:
            orbs = client.orb_list(self.request)
        except Exception:
            if self.live:
                raise
            self.get_table().unavailable = True
            exceptions.handle(self.request, _('Unable to retrieve orbs.'))
            return []
        # Deleted orbs hold no resources; their history stays in
        # `GET /v1/orbs?status=DELETED`.
        return [orb for orb in orbs if orb.status != 'DELETED']


class DetailView(LiveViewMixin, views.HorizonTemplateView):
    template_name = 'project/orbs/detail.html'
    fragment_template = 'project/orbs/_detail.html'
    page_title = _('Orb Details')

    @memoized.memoized_method
    def _get_data(self):
        try:
            return client.orb_get(self.request, self.kwargs['orb_id'])
        except Exception:
            if self.live:
                raise
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
