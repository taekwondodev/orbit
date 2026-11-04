import unittest

import yaml

from orbit import egress


class TestParse(unittest.TestCase):

    def test_destination_is_a_single_host_with_protocol_and_port(self):
        self.assertEqual(egress.Destination('udp', '10.0.0.2', 53),
                         egress.parse_destination('udp:10.0.0.2:53'))

    def test_destination_must_not_be_a_network_or_lack_a_part(self):
        for value in ('tcp:10.0.0.0/8:443', 'tcp:10.0.0.5', 'icmp:10.0.0.5:443',
                      'tcp:git.example.com:443', 'tcp:2001:db8::1:443',
                      'tcp:10.0.0.5:0', 'tcp:10.0.0.5:65536',
                      'tcp:10.0.0.5:https', 'tcp:10.0.0.5:\u00b2',
                      'tcp::443', 'tcp:0.0.0.0:443', 'tcp:127.0.0.1:443',
                      'udp:224.0.0.251:5353', 'udp:255.255.255.255:67'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    egress.parse_destination(value)

    def test_proxy_is_a_tcp_host_and_port(self):
        self.assertEqual(egress.Destination('tcp', '172.24.4.1', 4750),
                         egress.parse_proxy('172.24.4.1:4750'))

    def test_proxy_must_not_be_a_network(self):
        for value in ('172.24.4.0/24:4750', '172.24.4.1', 'proxy:4750'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    egress.parse_proxy(value)


class TestRules(unittest.TestCase):

    def test_nothing_listed_adds_no_rule(self):
        self.assertEqual([], egress.rules([], None))

    def test_each_destination_and_the_proxy_open_one_host_and_port(self):
        mirror = egress.Destination('tcp', '10.0.0.5', 443)
        proxy = egress.Destination('tcp', '172.24.4.1', 4750)

        self.assertEqual(
            [{'direction': 'egress', 'ethertype': 'IPv4', 'protocol': 'tcp',
              'remote_ip_prefix': '10.0.0.5/32',
              'port_range_min': 443, 'port_range_max': 443},
             {'direction': 'egress', 'ethertype': 'IPv4', 'protocol': 'tcp',
              'remote_ip_prefix': '172.24.4.1/32',
              'port_range_min': 4750, 'port_range_max': 4750}],
            egress.rules([mirror], proxy))

    def test_a_destination_listed_twice_opens_one_rule(self):
        # Neutron refuses a rule identical to one the group already has.
        proxy = egress.Destination('tcp', '172.24.4.1', 4750)

        self.assertEqual(1, len(egress.rules([proxy, proxy], proxy)))


class TestUserData(unittest.TestCase):

    def test_without_a_proxy_there_is_no_user_data(self):
        mirror = egress.Destination('tcp', '10.0.0.5', 443)

        self.assertEqual('', egress.user_data([mirror], None))

    def test_proxy_configures_sshd_sudo_and_apt(self):
        mirror = egress.Destination('tcp', '10.0.0.5', 443)
        proxy = egress.Destination('tcp', '172.24.4.1', 4750)

        text = egress.user_data([mirror], proxy)

        self.assertTrue(text.startswith('#cloud-config\n'))
        files = {f['path']: f for f in yaml.safe_load(text)['write_files']}
        # Readable by sshd, sudo and apt whatever the initializer's defaults.
        self.assertEqual({'root:root'}, {f['owner'] for f in files.values()})
        url = 'http://172.24.4.1:4750'
        # The proxy refuses private addresses, so listed ones bypass it.
        bypass = 'localhost,127.0.0.1,::1,10.0.0.5'
        # Clients run commands without a login shell, and sshd may not use
        # PAM: sshd sets the environment itself.
        self.assertEqual(
            f'SetEnv http_proxy={url} https_proxy={url} no_proxy={bypass} '
            f'HTTP_PROXY={url} HTTPS_PROXY={url} NO_PROXY={bypass}\n',
            files['/etc/ssh/sshd_config.d/90-orbit-proxy.conf']['content'])
        sudo = files['/etc/sudoers.d/90-orbit-proxy']
        self.assertEqual('0440', sudo['permissions'])
        self.assertEqual(
            'Defaults env_keep += "http_proxy https_proxy no_proxy '
            'HTTP_PROXY HTTPS_PROXY NO_PROXY"\n', sudo['content'])
        self.assertEqual(
            f'Acquire::http::Proxy "{url}";\n'
            f'Acquire::https::Proxy "{url}";\n'
            'Acquire::http::Proxy::10.0.0.5 "DIRECT";\n'
            'Acquire::https::Proxy::10.0.0.5 "DIRECT";\n',
            files['/etc/apt/apt.conf.d/90orbit-proxy']['content'])

    def test_proxy_alone_is_bypassed_only_for_the_machine_itself(self):
        proxy = egress.Destination('tcp', '172.24.4.1', 4750)

        config = yaml.safe_load(egress.user_data([], proxy))

        files = {f['path']: f for f in config['write_files']}
        sshd = files['/etc/ssh/sshd_config.d/90-orbit-proxy.conf']['content']
        self.assertIn(' no_proxy=localhost,127.0.0.1,::1 ', sshd)
