from oslo_config import cfg

service_option = cfg.BoolOpt('orbit', default=True,
                             help='orbit e installato e va provato.')

orbit_group = cfg.OptGroup(name='orbit', title='Opzioni dei test di orbit')

orbit_opts = [
    cfg.IntOpt('build_timeout', default=300,
               help='Secondi entro cui un orb deve arrivare in ACTIVE o '
                    'in DELETED.'),
    cfg.IntOpt('build_interval', default=5,
               help='Secondi fra due letture dell\'orb.'),
    cfg.DictOpt('size', default={'vcpus': '1', 'memory_mb': '512',
                                 'disk_gb': '1'},
                help='Taglia dell\'orb dei test: deve stare sull\'host.'),
    cfg.DictOpt('oversized_size', default={'vcpus': '1',
                                           'memory_mb': '16384',
                                           'disk_gb': '1'},
                help='Taglia che nessun host puo ospitare. Blazar confronta '
                     'la richiesta con processori, memoria e disco reali '
                     'dell\'host, senza sovrallocazione.'),
    cfg.BoolOpt('ssh_check', default=True,
                help='Entra nell\'orb in SSH prima di cancellarlo.'),
]
