"""Opzioni di configurazione di orbit, lette da /etc/orbit/orbit.conf."""

from oslo_config import cfg
from oslo_db import options as db_options
from oslo_log import log

CONF = cfg.CONF

orbs_opts = [
    cfg.IntOpt('max_vcpus', default=8, min=1,
               help='Processori massimi di un orb.'),
    cfg.IntOpt('max_memory_mb', default=16384, min=1,
               help='Memoria massima di un orb, in MiB.'),
    cfg.IntOpt('max_disk_gb', default=80, min=1,
               help='Disco massimo di un orb, in GiB.'),
    cfg.StrOpt('default_image',
               help='Immagine usata quando la richiesta non ne indica una. '
                    'Senza valore, la richiesta deve indicarla.'),
    cfg.StrOpt('default_ssh_user', default='ubuntu',
               help='Utente SSH restituito per le immagini senza una voce '
                    'in ssh_users.'),
    cfg.DictOpt('ssh_users', default={},
                help='Utente SSH per immagine, come immagine:utente. '
                     'L\'utente dipende dall\'immagine e il client non deve '
                     'indovinarlo.'),
    cfg.StrOpt('lease_end_date', default='2099-12-31 23:59',
               help='Data di fine dei lease, nel formato di Blazar '
                    '"AAAA-MM-GG hh:mm". Non e una scadenza: Blazar esige '
                    'una fine, l\'orb finisce con DELETE (docs/adr/0003).'),
    cfg.IntOpt('creation_timeout', default=120, min=1,
               help='Secondi entro cui la prenotazione deve attivarsi e lo '
                    'stack essere creato. Oltre, il compito di creazione '
                    'rinuncia e un orb senza stack risulta interrotto.'),
    cfg.FloatOpt('reservation_poll_interval', default=2.0, min=0.1,
                 help='Secondi fra due letture del lease mentre si attende '
                      'la prenotazione attiva.'),
    cfg.StrOpt('network', default='private',
               help='Rete di progetto a cui collegare gli orb.'),
    cfg.StrOpt('public_network', default='public',
               help='Rete esterna da cui prendere l\'indirizzo raggiungibile.'),
    cfg.StrOpt('ssh_allowed_cidr', default='0.0.0.0/0',
               help='Da dove e ammesso l\'accesso SSH agli orb.'),
]

CONF.register_opts(orbs_opts, group='orbs')
db_options.set_defaults(CONF)


def parse_args(argv, default_config_files=None):
    log.register_options(CONF)
    CONF(argv, project='orbit', default_config_files=default_config_files)
    log.setup(CONF, 'orbit')


def list_opts():
    return [('orbs', orbs_opts)]
