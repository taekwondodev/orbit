"""orbit's configuration options, read from /etc/orbit/orbit.conf."""

from oslo_config import cfg
from oslo_db import options as db_options
from oslo_log import log

CONF = cfg.CONF

orbs_opts = [
    cfg.IntOpt('max_vcpus', default=8, min=1,
               help='Maximum processors of an orb.'),
    cfg.IntOpt('max_memory_mb', default=16384, min=1,
               help='Maximum memory of an orb, in MiB.'),
    cfg.IntOpt('max_disk_gb', default=80, min=1,
               help='Maximum disk of an orb, in GiB.'),
    cfg.StrOpt('default_image',
               help='Image used when the request does not name one. '
                    'Without a value, the request must name it.'),
    cfg.StrOpt('default_ssh_user', default='ubuntu',
               help='SSH user returned for images without an entry '
                    'in ssh_users.'),
    cfg.DictOpt('ssh_users', default={},
                help='SSH user per image, as image:user. '
                     'The user depends on the image and the client must not '
                     'have to guess it.'),
    cfg.StrOpt('lease_end_date', default='2099-12-31 23:59',
               help='End date of the leases, in the Blazar format '
                    '"YYYY-MM-DD hh:mm". Not an expiry: Blazar requires '
                    'an end, the orb ends with DELETE (docs/adr/0003).'),
    cfg.IntOpt('creation_timeout', default=120, min=1,
               help='Seconds within which the reservation must activate and '
                    'the stack be created. Beyond that, the creation task '
                    'gives up and an orb without a stack counts as '
                    'interrupted.'),
    cfg.FloatOpt('reservation_poll_interval', default=2.0, min=0.1,
                 help='Seconds between two reads of the lease while waiting '
                      'for the reservation to be active.'),
    cfg.IntOpt('api_timeout', default=60, min=1,
               help='Maximum seconds to wait for a response from Blazar, '
                    'Heat or Nova. Deleting an active lease responds only '
                    'after the machine is destroyed.'),
    cfg.StrOpt('public_network', default='public',
               help='External network that the router of each orb '
                    'connects to and that provides the reachable address.'),
    cfg.StrOpt('ssh_allowed_cidr', default='0.0.0.0/0',
               help='Where SSH access to the orbs is allowed from.'),
]

CONF.register_opts(orbs_opts, group='orbs')
db_options.set_defaults(CONF)


def parse_args(argv, default_config_files=None):
    log.register_options(CONF)
    CONF(argv, project='orbit', default_config_files=default_config_files)
    log.setup(CONF, 'orbit')


def list_opts():
    return [('orbs', orbs_opts)]
