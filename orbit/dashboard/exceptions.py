"""Errors of the orbit API as the Orbs panel raises them.

Registered with Horizon by the panel's enabled file, which Horizon imports
while reading its settings: this module must import nothing from Horizon.
"""


class OrbitError(Exception):
    """orbit refused the request or did not answer; carries its message."""


class OrbNotFound(OrbitError):
    pass


class OrbitUnauthorized(OrbitError):
    pass
