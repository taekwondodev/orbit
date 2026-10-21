from oslo_config import cfg

service_option = cfg.BoolOpt('orbit', default=True,
                             help='orbit is installed and must be tested.')

orbit_group = cfg.OptGroup(name='orbit', title='orbit test options')

orbit_opts = [
    cfg.IntOpt('build_timeout', default=300,
               help='Seconds within which an orb must reach ACTIVE or '
                    'DELETED.'),
    cfg.IntOpt('build_interval', default=5,
               help='Seconds between two reads of the orb.'),
    cfg.DictOpt('size', default={'vcpus': '1', 'memory_mb': '512',
                                 'disk_gb': '1'},
                help='Size of the test orb: it must fit on the host.'),
    cfg.DictOpt('oversized_size', default={'vcpus': '1',
                                           'memory_mb': '16384',
                                           'disk_gb': '1'},
                help='Size no host can hold. Blazar compares the request '
                     'with the real processors, memory and disk of the '
                     'host, without overcommit.'),
    cfg.BoolOpt('ssh_check', default=True,
                help='Log into the orb over SSH before deleting it.'),
]
