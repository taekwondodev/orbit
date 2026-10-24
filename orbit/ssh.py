"""OpenSSH public keys: the client's, from the request, and the orb's host
keys, from the machine's console."""

import base64
import binascii

# A 16384-bit RSA key takes about 2800 characters.
MAX_KEY_LENGTH = 8192
MAX_HOST_KEYS = 8

KEY_TYPES = ('ssh-ed25519', 'ssh-rsa', 'ecdsa-sha2-nistp256',
             'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521',
             'sk-ssh-ed25519@openssh.com',
             'sk-ecdsa-sha2-nistp256@openssh.com')

# Printed at boot by cloud-init (keys_to_console) and by CirrOS
# (cirros-status).
_BEGIN = '-----BEGIN SSH HOST KEY KEYS-----'
_END = '-----END SSH HOST KEY KEYS-----'


def public_key(text):
    """``text`` without surrounding blanks if it is a single OpenSSH public
    key, otherwise None."""
    key = text.strip()
    parts = key.split()
    if (len(key) > MAX_KEY_LENGTH or '\n' in key or '\r' in key
            or len(parts) < 2 or parts[0] not in KEY_TYPES):
        return None
    try:
        base64.b64decode(parts[1], validate=True)
    except binascii.Error:
        return None
    return key


def host_keys(console):
    """The host keys of the first block in the console, as ``type base64``.

    None while the block is incomplete or holds no key. Only the first block
    counts: it is printed at boot, when only the image's code runs, while a
    process inside the orb can print a forged one later. The console is
    written by the machine, so lines that are not keys are skipped and the
    keys are bounded.
    """
    lines = iter(console.splitlines())
    for line in lines:
        if line.strip() == _BEGIN:
            break
    else:
        return None
    keys = []
    for line in lines:
        if line.strip() == _END:
            return tuple(keys) or None
        key = public_key(line)
        if key is not None and len(keys) < MAX_HOST_KEYS:
            keys.append(' '.join(key.split()[:2]))
    return None
