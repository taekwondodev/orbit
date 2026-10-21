"""openstackclient plugin: adds the ``openstack orb`` commands."""

from orbit.osc import client

DEFAULT_API_VERSION = '1'

# Required by the openstackclient plugin interface.
API_NAME = 'orbit'
API_VERSION_OPTION = 'os_orbit_api_version'
API_VERSIONS = {'1': 'orbit.osc.client.Client'}


def make_client(instance):
    return client.Client(instance.session,
                         region_name=instance.region_name,
                         interface=instance.interface)


def build_option_parser(parser):
    parser.add_argument(
        '--os-orbit-api-version',
        metavar='<orbit-api-version>',
        default=DEFAULT_API_VERSION,
        help=f'orbit API version, default '
             f'{DEFAULT_API_VERSION}.')
    return parser
