"""Horizon's test settings with the Orbs panel enabled, as heat-dashboard's."""

import openstack_dashboard.enabled
from openstack_dashboard.test.settings import *  # noqa: F401,F403
from openstack_dashboard.test.settings import HORIZON_CONFIG
from openstack_dashboard.test.settings import INSTALLED_APPS
from openstack_dashboard.utils import settings as settings_utils

import orbit.dashboard.enabled

# update_dashboards fills them again; left in place they log a deprecation.
HORIZON_CONFIG.pop('dashboards', None)
HORIZON_CONFIG.pop('default_dashboard', None)

settings_utils.update_dashboards(
    [openstack_dashboard.enabled, orbit.dashboard.enabled],
    HORIZON_CONFIG,
    INSTALLED_APPS,
)

# Horizon's test settings already added its own apps once.
INSTALLED_APPS = list(dict.fromkeys(INSTALLED_APPS))
