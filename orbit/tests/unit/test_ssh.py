import unittest

from orbit import ssh
from orbit.tests.unit import fakes

ED25519 = fakes.HOST_KEY_ED25519
ECDSA = fakes.HOST_KEY_ECDSA
BEGIN = '-----BEGIN SSH HOST KEY KEYS-----'
END = '-----END SSH HOST KEY KEYS-----'


def console(*lines):
    return '\n'.join(lines) + '\n'


class TestHostKeys(unittest.TestCase):

    def test_cloud_init_block_gives_its_keys_without_comments(self):
        self.assertEqual((ECDSA, ED25519), ssh.host_keys(fakes.CONSOLE))

    def test_cirros_block_gives_its_keys(self):
        cirros = console(
            '=== sshd host keys ===', BEGIN,
            f'{ECDSA} root@cirros', f'{ED25519} root@cirros', END,
            '=== network info ===')

        self.assertEqual((ECDSA, ED25519), ssh.host_keys(cirros))

    def test_line_interleaved_by_the_kernel_is_skipped(self):
        interleaved = console(
            BEGIN, ECDSA, '[   12.345678] random: crng init done', ED25519,
            END)

        self.assertEqual((ECDSA, ED25519), ssh.host_keys(interleaved))

    def test_only_the_first_block_counts(self):
        forged = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEZvcmdlZA=='

        self.assertEqual((ECDSA,), ssh.host_keys(console(
            BEGIN, ECDSA, END, BEGIN, forged, END)))

    def test_keys_not_published_yet(self):
        for text in ('', console('login:'), console(BEGIN, ECDSA),
                     console(BEGIN, 'not a key', 'ssh-dss AAAA', END)):
            with self.subTest(console=text):
                self.assertIsNone(ssh.host_keys(text))

    def test_keys_are_bounded(self):
        oversized = 'ssh-rsa ' + 'A' * 9000

        self.assertEqual((ED25519,), ssh.host_keys(console(
            BEGIN, oversized, ED25519, END)))
        self.assertEqual((ED25519,) * 8, ssh.host_keys(console(
            BEGIN, *[ED25519] * 9, END)))
