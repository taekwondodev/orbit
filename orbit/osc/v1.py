"""I comandi ``openstack orb create|list|show|delete``."""

import time

from osc_lib.command import command
from osc_lib import exceptions

_FIELDS = ('id', 'status', 'vcpus', 'memory_mb', 'disk_gb', 'image',
           'ssh_host', 'ssh_user', 'fault', 'created_at')
_FINAL_STATUSES = ('ACTIVE', 'ERROR', 'DELETED')


def _row(orb, fields=_FIELDS):
    flat = dict(orb, **orb['size'])
    return tuple(flat.get(field) for field in fields)


class CreateOrb(command.ShowOne):
    """Crea un orb: prenota la capacità e avvia la costruzione."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument('--vcpus', type=int, required=True,
                            help='Processori.')
        parser.add_argument('--memory', type=int, required=True,
                            metavar='<MiB>', help='Memoria in MiB.')
        parser.add_argument('--disk', type=int, required=True,
                            metavar='<GiB>', help='Disco in GiB.')
        parser.add_argument('--public-key', required=True, metavar='<file>',
                            help='File della chiave pubblica SSH da '
                                 'installare, per esempio '
                                 '~/.ssh/id_ed25519.pub.')
        parser.add_argument('--image', help='Immagine; senza, quella '
                                            'predefinita del servizio.')
        parser.add_argument('--wait', action='store_true',
                            help='Attende che l\'orb sia ACTIVE o ERROR.')
        return parser

    def take_action(self, parsed_args):
        try:
            with open(parsed_args.public_key) as key_file:
                public_key = key_file.read()
        except OSError as e:
            raise exceptions.CommandError(
                f'Chiave pubblica non leggibile: {e}') from e
        client = self.app.client_manager.orbit
        orb = client.create({'vcpus': parsed_args.vcpus,
                             'memory_mb': parsed_args.memory,
                             'disk_gb': parsed_args.disk},
                            public_key, parsed_args.image)
        if parsed_args.wait:
            orb = _wait(client, orb)
        return _FIELDS, _row(orb)


class ListOrb(command.Lister):
    """Elenca gli orb del progetto."""

    _COLUMNS = ('id', 'status', 'vcpus', 'memory_mb', 'disk_gb', 'ssh_host')

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument('--status', help='Solo gli orb in questo stato.')
        return parser

    def take_action(self, parsed_args):
        orbs = self.app.client_manager.orbit.list(parsed_args.status)
        return self._COLUMNS, [_row(orb, self._COLUMNS) for orb in orbs]


class ShowOrb(command.ShowOne):
    """Mostra un orb com'e adesso."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument('orb', help='Identificativo dell\'orb.')
        return parser

    def take_action(self, parsed_args):
        return _FIELDS, _row(self.app.client_manager.orbit.get(
            parsed_args.orb))


class DeleteOrb(command.Command):
    """Cancella uno o più orb, con tutte le loro risorse."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument('orbs', nargs='+', metavar='<orb>',
                            help='Identificativi degli orb.')
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
                f'{len(failed)} di {len(parsed_args.orbs)} orb non '
                f'cancellati.')


def _wait(client, orb, interval=2, sleep=time.sleep):
    while orb['status'] not in _FINAL_STATUSES:
        sleep(interval)
        orb = client.get(orb['id'])
    return orb
