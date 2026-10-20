"""Opzioni di configurazione di orbit, lette da /etc/orbit/orbit.conf."""

from oslo_config import cfg
from oslo_log import log

CONF = cfg.CONF


def parse_args(argv, default_config_files=None):
    log.register_options(CONF)
    CONF(argv, project='orbit', default_config_files=default_config_files)
    log.setup(CONF, 'orbit')


def list_opts():
    return []
