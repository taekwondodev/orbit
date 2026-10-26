"""orbit's configuration options, read from /etc/orbit/orbit.conf."""

import ipaddress

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
    cfg.IntOpt('ready_timeout', default=600, min=1,
               help='Seconds, counted from the creation request like '
                    'creation_timeout, within which the machine must boot '
                    'and print its SSH host keys on the console. Beyond '
                    'that, the orb goes to ERROR. It includes the wait for '
                    'the reservation and the stack, so it must be greater '
                    'than creation_timeout, well above it to leave time '
                    'for the boot.'),
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
    cfg.IntOpt('ssh_min_prefix', default=24, min=1, max=32,
               help='Narrowest prefix length a request may use for its SSH '
                    'network: a client connects from one address or a '
                    'small NAT pool, so wider networks are rejected. Lower '
                    'it only for a client that needs a wider range.'),
    cfg.StrOpt('ssh_allowed_cidr',
               help='Cap on the networks SSH to the orbs may be admitted '
                    'from, as an IPv4 CIDR. Each creation request names its own '
                    'network, which must lie inside this one. Without a '
                    'value, any network but the whole Internet is '
                    'accepted.'),
]

CONF.register_opts(orbs_opts, group='orbs')
db_options.set_defaults(CONF)


def parse_args(argv, default_config_files=None):
    log.register_options(CONF)
    CONF(argv, project='orbit', default_config_files=default_config_files)
    log.setup(CONF, 'orbit')


class InvalidOption(ValueError):
    """An option orbit-api cannot run with."""


def check_api_options():
    """Refuse to serve with the options orbit-api cannot run with."""
    try:
        CONF.orbs.ssh_min_prefix
    except cfg.ConfigFileValueError as e:
        raise InvalidOption(f'[orbs] ssh_min_prefix: {e}') from e
    cap = CONF.orbs.ssh_allowed_cidr
    if cap is not None:
        try:
            ipaddress.IPv4Network(cap)
        except ValueError as e:
            raise InvalidOption(
                f'[orbs] ssh_allowed_cidr is not an IPv4 network: {e}') from e
    if CONF.orbs.ready_timeout <= CONF.orbs.creation_timeout:
        raise InvalidOption(
            '[orbs] ready_timeout must be greater than creation_timeout: '
            'both count from the creation request, and the machine boots '
            'only after the stack is created.')


def list_opts():
    return [('orbs', orbs_opts)]
