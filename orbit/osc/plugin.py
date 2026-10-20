"""Plugin di openstackclient: aggiunge i comandi ``openstack orb``."""

from orbit.osc import client

DEFAULT_API_VERSION = '1'

# Richiesti dall'interfaccia dei plugin di openstackclient.
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
        help=f'Versione della API di orbit, predefinita '
             f'{DEFAULT_API_VERSION}.')
    return parser
