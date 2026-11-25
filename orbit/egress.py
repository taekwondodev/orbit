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
        return {
            'direction': 'egress',
            'ethertype': 'IPv4',
            'protocol': self.protocol,
            'remote_ip_prefix': f'{self.address}/32',
            'port_range_min': self.port,
            'port_range_max': self.port,
        }


def parse_destination(value):
    try:
        protocol, address, port = value.split(':')
    except ValueError:
        raise ValueError(f'{value!r} is not protocol:address:port') from None
    if protocol not in PROTOCOLS:
        raise ValueError(
            f'{value!r}: protocol must be one of {", ".join(PROTOCOLS)}'
        )
    return Destination(protocol, _address(value, address), _port(value, port))


def parse_proxy(value):
    try:
        address, port = value.split(':')
    except ValueError:
        raise ValueError(f'{value!r} is not address:port') from None
    return Destination('tcp', _address(value, address), _port(value, port))


def _address(value, address):
    try:
        parsed = ipaddress.IPv4Address(address)
    except ValueError:
        raise ValueError(
            f'{value!r}: {address!r} is not a single IPv4 address'
        ) from None
    if (
        parsed.is_unspecified
        or parsed.is_loopback
        or parsed.is_multicast
        or parsed == ipaddress.IPv4Address('255.255.255.255')
    ):
        raise ValueError(f'{value!r}: {address!r} is not a single host')
    return str(parsed)


def _port(value, port):
    if not (port.isascii() and port.isdigit()) or not 1 <= int(port) <= 65535:
        raise ValueError(f'{value!r}: {port!r} is not a port')
    return int(port)


def rules(destinations, proxy):
    listed = list(destinations) + ([proxy] if proxy else [])
    # Neutron refuses a rule identical to one the group already has.
    return [destination.rule() for destination in dict.fromkeys(listed)]


def user_data(destinations, proxy):
    # Clients run commands over SSH without a login shell, and sshd may not
    # use PAM, so sshd itself sets the environment of every session; sudo
    # keeps it. tiny-cloud writes the files before sshd starts. Listed destinations bypass the proxy, which refuses private
    # addresses.
    if proxy is None:
        return ''
    url = f'http://{proxy.address}:{proxy.port}'
    bypass = ','.join(
        ['localhost', '127.0.0.1', '::1'] + [d.address for d in destinations]
    )
    environment = (
        ('http_proxy', url),
        ('https_proxy', url),
        ('no_proxy', bypass),
        ('HTTP_PROXY', url),
        ('HTTPS_PROXY', url),
        ('NO_PROXY', bypass),
    )
    config = {
        'write_files': [
            _root_file(
                '/etc/ssh/sshd_config.d/90-orbit-proxy.conf',
                '0644',
                _sshd_config(environment),
            ),
            _root_file(
                '/etc/sudoers.d/90-orbit-proxy', '0440', _sudoers(environment)
            ),
        ]
    }
    # cloud-config is YAML, of which JSON is a subset.
    return '#cloud-config\n' + json.dumps(config, indent=2) + '\n'


def _root_file(path, permissions, content):
    return {
        'path': path,
        'owner': 'root:root',
        'permissions': permissions,
        'content': content,
    }


def _sshd_config(environment):
    return (
        'SetEnv '
        + ' '.join(f'{name}={value}' for name, value in environment)
        + '\n'
    )


def _sudoers(environment):
    return (
        'Defaults env_keep += "'
        + ' '.join(name for name, _ in environment)
        + '"\n'
    )
