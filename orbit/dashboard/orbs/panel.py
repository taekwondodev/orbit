from django.utils.translation import gettext_lazy as _

import horizon


class Orbs(horizon.Panel):
    name = _('Orbs')
    slug = 'orbs'
    permissions = ('openstack.services.orbit',)
