"""The ``openstack orb create|list|show|delete`` commands."""

import time

from osc_lib.cli import format_columns
from osc_lib.command import command
from osc_lib import exceptions

_FIELDS = ('id', 'status', 'vcpus', 'memory_mb', 'disk_gb', 'image',
           'ssh_host', 'ssh_user', 'ssh_host_keys', 'fault', 'created_at')
_FINAL_STATUSES = ('ACTIVE', 'ERROR', 'DELETED')


def _row(orb, fields=_FIELDS):
    flat = dict(orb, **orb['size'])
    if flat.get('ssh_host_keys') is not None:
        # A list in -f json, one string in the table.
        flat['ssh_host_keys'] = format_columns.ListColumn(
            flat['ssh_host_keys'])
    return tuple(flat.get(field) for field in fields)


class CreateOrb(command.ShowOne):
    """Create an orb: reserve the capacity and start the build."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument('--vcpus', type=int, required=True,
                            help='Processors.')
        parser.add_argument('--memory', type=int, required=True,
                            metavar='<MiB>', help='Memory in MiB.')
        parser.add_argument('--disk', type=int, required=True,
                            metavar='<GiB>', help='Disk in GiB.')
        parser.add_argument('--public-key', required=True, metavar='<file>',
                            help='File of the SSH public key to '
                                 'install, for example '
                                 '~/.ssh/id_ed25519.pub.')
        parser.add_argument('--image', help='Image; without it, the '
                                            'service default.')
        parser.add_argument('--wait', action='store_true',
                            help='Wait until the orb is ACTIVE; fail if '
                                 'it ends in another status.')
        return parser

    def take_action(self, parsed_args):
        try:
            with open(parsed_args.public_key) as key_file:
                public_key = key_file.read()
        except OSError as e:
            raise exceptions.CommandError(
                f'Public key not readable: {e}') from e
        client = self.app.client_manager.orbit
        orb = client.create({'vcpus': parsed_args.vcpus,
                             'memory_mb': parsed_args.memory,
                             'disk_gb': parsed_args.disk},
                            public_key, parsed_args.image)
        if parsed_args.wait:
            orb = _wait(client, orb)
            # Like server create --wait: a script must see the failure.
            if orb['status'] != 'ACTIVE':
                raise exceptions.CommandError(
                    f"Orb {orb['id']} ended in {orb['status']}: "
                    f"{orb['fault']}")
        return _FIELDS, _row(orb)


class ListOrb(command.Lister):
    """List the project's orbs."""

    _COLUMNS = ('id', 'status', 'vcpus', 'memory_mb', 'disk_gb', 'ssh_host')

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument('--status', help='Only the orbs in this status.')
        return parser

    def take_action(self, parsed_args):
        orbs = self.app.client_manager.orbit.list(parsed_args.status)
        return self._COLUMNS, [_row(orb, self._COLUMNS) for orb in orbs]


class ShowOrb(command.ShowOne):
    """Show an orb as it is now."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument('orb', help='Identifier of the orb.')
        return parser

    def take_action(self, parsed_args):
        return _FIELDS, _row(self.app.client_manager.orbit.get(
            parsed_args.orb))


class DeleteOrb(command.Command):
    """Delete one or more orbs, with all their resources."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument('orbs', nargs='+', metavar='<orb>',
                            help='Identifiers of the orbs.')
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.orbit
        failed = []
        for orb_id in parsed_args.orbs:
            try:
                client.delete(orb_id)
            except exceptions.CommandError as e:
                self.app.stderr.write(f'{orb_id}: {e}\n')
                failed.append(orb_id)
        if failed:
            raise exceptions.CommandError(
                f'{len(failed)} of {len(parsed_args.orbs)} orbs not '
                f'deleted.')


def _wait(client, orb, interval=2, sleep=time.sleep):
    while orb['status'] not in _FINAL_STATUSES:
        sleep(interval)
        orb = client.get(orb['id'])
    return orb
