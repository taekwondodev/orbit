from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from horizon import exceptions
from horizon import tables
from horizon import views
from horizon.utils import memoized

from orbit.dashboard import client
from orbit.dashboard.exceptions import OrbitError
from orbit.dashboard.exceptions import OrbitUnauthorized
from orbit.dashboard.exceptions import OrbNotFound
from orbit.dashboard.orbs import overview
from orbit.dashboard.orbs import tables as orbs_tables

# Rows needing attention first: failures, then orbs on their way up.
ROW_ORDER = {
    'ERROR': 0,
    'RESERVING': 1,
    'BUILDING': 1,
    'ACTIVE': 2,
    'DELETING': 3,
}

# What each of the table's STEPS waits for, shown on the detail page.
STEP_HELP = (
    _('Blazar reserves the capacity'),
    _('Heat builds the network and the machine'),
    _('Host keys published, ready for SSH'),
)


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
        response = JsonResponse(
            {
                'html': render_to_string(
                    self.fragment_template, context, request=self.request
                )
            }
        )
        response['Cache-Control'] = 'no-store'
        return response


class IndexView(LiveViewMixin, tables.DataTableView):
    template_name = 'project/orbs/index.html'
    fragment_template = 'project/orbs/_list.html'
    table_class = orbs_tables.OrbsTable
    page_title = _('Orbs')

    # Every orb of the list read, DELETED ones included; None when the
    # read failed, so the summary does not report an empty project.
    orbs = None

    def get_data(self):
        try:
            self.orbs = client.orb_list(self.request)
        except Exception:
            if self.live:
                raise
            self.get_table().unavailable = True
            exceptions.handle(self.request, _('Unable to retrieve orbs.'))
            return []
        # Deleted orbs hold no resources: they count only in the summary.
        rows = [orb for orb in self.orbs if orb.status != 'DELETED']
        rows.sort(key=lambda orb: orb.created_at, reverse=True)
        rows.sort(key=lambda orb: ROW_ORDER.get(orb.status, len(ROW_ORDER)))
        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.orbs is not None:
            context['overview'] = overview.summarize(
                self.orbs, timezone.localdate()
            )
        return context


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
                redirect=reverse('horizon:project:orbs:index'),
            )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orb = self._get_data()
        context['orb'] = orb
        context['status_badge'] = orbs_tables.status_badge(orb.status)
        states = orbs_tables.step_states(orb.status)
        if states is not None:
            context['steps'] = [
                {
                    'label': orbs_tables.status_label(status),
                    'help': text,
                    'state': state,
                }
                for status, text, state in zip(
                    orbs_tables.STEPS, STEP_HELP, states
                )
            ]
        return context
