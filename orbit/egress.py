"""The destinations an orb may open connections to (docs/adr/0009).

The template denies all outbound traffic; the operator lists single hosts
with protocol and port, and an egress proxy for external destinations. This
module turns those options into the orb's egress rules and the cloud-config
user data that points its tools at the proxy.
"""

import dataclasses
import ipaddress
import json

PROTOCOLS = ('tcp', 'udp')


@dataclasses.dataclass(frozen=True)
class Destination:
    protocol: str
    address: str
    port: int

    def rule(self):
        return {'direction': 'egress', 'ethertype': 'IPv4',
                'protocol': self.protocol,
                'remote_ip_prefix': f'{self.address}/32',
                'port_range_min': self.port, 'port_range_max': self.port}


def parse_destination(value):
    """Parse protocol:address:port, with a single IPv4 address."""
    try:
        protocol, address, port = value.split(':')
    except ValueError:
        raise ValueError(f'{value!r} is not protocol:address:port') from None
    if protocol not in PROTOCOLS:
        raise ValueError(f'{value!r}: protocol must be one of '
                         f'{", ".join(PROTOCOLS)}')
    return Destination(protocol, _address(value, address),
                       _port(value, port))


def parse_proxy(value):
    """Parse address:port, the TCP endpoint of an HTTP egress proxy."""
    try:
        address, port = value.split(':')
    except ValueError:
        raise ValueError(f'{value!r} is not address:port') from None
    return Destination('tcp', _address(value, address), _port(value, port))


def _address(value, address):
    try:
        parsed = ipaddress.IPv4Address(address)
    except ValueError:
        raise ValueError(f'{value!r}: {address!r} is not a single IPv4 '
                         'address') from None
    if (parsed.is_unspecified or parsed.is_loopback or parsed.is_multicast
            or parsed == ipaddress.IPv4Address('255.255.255.255')):
        raise ValueError(f'{value!r}: {address!r} is not a single host')
    return str(parsed)


def _port(value, port):
    if not (port.isascii() and port.isdigit()) or not 1 <= int(port) <= 65535:
        raise ValueError(f'{value!r}: {port!r} is not a port')
    return int(port)


def rules(destinations, proxy):
    """Egress rules of the orb's security group, beside the template's own."""
    listed = list(destinations) + ([proxy] if proxy else [])
    # Neutron refuses a rule identical to one the group already has.
    return [destination.rule() for destination in dict.fromkeys(listed)]


def user_data(destinations, proxy):
    """cloud-config user data that routes the orb's tools through the proxy.

    cloud-init and tiny-cloud both write it before sshd starts. Clients run
    commands over SSH without a login shell, and sshd may not use PAM, so
    sshd itself sets the environment of every session; sudo keeps it. Listed
    destinations bypass the proxy, which refuses private addresses.
    """
    if proxy is None:
        return ''
    url = f'http://{proxy.address}:{proxy.port}'
    bypass = ','.join(['localhost', '127.0.0.1', '::1'] +
                      [d.address for d in destinations])
    environment = (('http_proxy', url), ('https_proxy', url),
                   ('no_proxy', bypass), ('HTTP_PROXY', url),
                   ('HTTPS_PROXY', url), ('NO_PROXY', bypass))
    sshd = 'SetEnv ' + ' '.join(f'{name}={value}'
                                for name, value in environment) + '\n'
    sudo = ('Defaults env_keep += "' +
            ' '.join(name for name, _ in environment) + '"\n')
    apt = (f'Acquire::http::Proxy "{url}";\n'
           f'Acquire::https::Proxy "{url}";\n' +
           ''.join(f'Acquire::http::Proxy::{d.address} "DIRECT";\n'
                   f'Acquire::https::Proxy::{d.address} "DIRECT";\n'
                   for d in destinations))
    config = {'write_files': [
        {'path': '/etc/ssh/sshd_config.d/90-orbit-proxy.conf',
         'owner': 'root:root', 'permissions': '0644', 'content': sshd},
        {'path': '/etc/sudoers.d/90-orbit-proxy',
         'owner': 'root:root', 'permissions': '0440', 'content': sudo},
        {'path': '/etc/apt/apt.conf.d/90orbit-proxy',
         'owner': 'root:root', 'permissions': '0644', 'content': apt},
    ]}
    # cloud-config is YAML, of which JSON is a subset.
    return '#cloud-config\n' + json.dumps(config, indent=2) + '\n'
