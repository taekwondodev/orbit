"""Horizon imports this module through the panel's enabled file while reading
its settings: it must import nothing from Horizon.
"""


class OrbitError(Exception):
    pass


class OrbNotFound(OrbitError):
    pass


class OrbitUnauthorized(OrbitError):
    pass
