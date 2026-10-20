import os

from tempest import config
from tempest.test_discover import plugins

from orbit.tests.tempest import config as orbit_config


class OrbitTempestPlugin(plugins.TempestPlugin):

    def load_tests(self):
        here = os.path.dirname(os.path.abspath(__file__))
        top_level = os.path.dirname(os.path.dirname(os.path.dirname(here)))
        return os.path.join(here, 'tests'), top_level

    def register_opts(self, conf):
        config.register_opt_group(conf, config.service_available_group,
                                  [orbit_config.service_option])
        config.register_opt_group(conf, orbit_config.orbit_group,
                                  orbit_config.orbit_opts)

    def get_opt_lists(self):
        return [(orbit_config.orbit_group.name, orbit_config.orbit_opts),
                ('service_available', [orbit_config.service_option])]
