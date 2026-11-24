import horizon
from django.utils.translation import gettext_lazy as _


class Orbs(horizon.Panel):
    name = _('Orbs')
    slug = 'orbs'
    permissions = ('openstack.services.orbit',)
