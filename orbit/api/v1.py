"""The HTTP resources of /v1. The contract is in docs/design/api.md."""

import ipaddress

import flask
from werkzeug import exceptions as http_exc

from orbit import clients
from orbit.conf import CONF
from orbit import orb as orb_model
from orbit import service
from orbit import ssh

blueprint = flask.Blueprint('v1', __name__)

# The image column is 255 long.
_MAX_IMAGE_LENGTH = 255


def _orbs():
    return flask.current_app.config['ORBS']


def _context():
    environ = flask.request.environ
    project_id = environ.get('HTTP_X_PROJECT_ID')
    if not project_id:
        raise http_exc.Forbidden('A project-scoped token is required.')
    return service.Context(project_id=project_id,
                           user_id=environ.get('HTTP_X_USER_ID'),
                           auth=environ.get('keystone.token_auth'))


@blueprint.post('/orbs')
def create_orb():
    request = _create_request(flask.request.get_json(silent=True))
    observed = _orbs().create(_context(), request)
    return _view(observed), 202


@blueprint.get('/orbs')
def list_orbs():
    status = flask.request.args.get('status')
    if status is not None:
        try:
            status = orb_model.Status(status)
        except ValueError:
            raise http_exc.BadRequest(f'Unknown status: {status}')
    return {'orbs': [_view(o) for o in _orbs().list(_context(), status)]}


@blueprint.get('/orbs/<orb_id>')
def show_orb(orb_id):
    observed = _orbs().get(_context(), orb_id)
    if observed is None:
        raise http_exc.NotFound(f'Orb {orb_id} not found.')
    return _view(observed)


@blueprint.delete('/orbs/<orb_id>')
def delete_orb(orb_id):
    observed = _orbs().delete(_context(), orb_id)
    if observed is None:
        raise http_exc.NotFound(f'Orb {orb_id} not found.')
    return _view(observed), 202


@blueprint.errorhandler(clients.CapacityExhausted)
def _capacity_exhausted(error):
    return _error(409, 'Capacity exhausted: no host has room for the '
                       'requested size.')


@blueprint.errorhandler(clients.Rejected)
def _rejected(error):
    # A downstream 401 or 403 concerns the requester's token or roles; any
    # other rejection is a response the service cannot handle.
    code = error.code if error.code in (401, 403) else 502
    return _error(code, f'Request rejected: {error}')


@blueprint.errorhandler(clients.Unavailable)
def _unavailable(error):
    return _error(503, f'{str(error).capitalize()}.')


@blueprint.errorhandler(http_exc.HTTPException)
def _http_error(error):
    return _error(error.code, error.description)


def _error(code, message):
    return {'error': {'code': code, 'message': message}}, code


def _create_request(body):
    if not isinstance(body, dict):
        raise http_exc.BadRequest('The body must be a JSON object.')
    return service.CreateRequest(
        size=_size(body.get('size')),
        public_key=_public_key(body.get('public_key')),
        image=_image(body.get('image')),
        ssh_allowed_cidr=_ssh_allowed_cidr(body.get('ssh_allowed_cidr')),
    )


def _size(size):
    if not isinstance(size, dict):
        raise http_exc.BadRequest(
            'size must specify vcpus, memory_mb and disk_gb.')
    limits = {'vcpus': CONF.orbs.max_vcpus,
              'memory_mb': CONF.orbs.max_memory_mb,
              'disk_gb': CONF.orbs.max_disk_gb}
    for field, limit in limits.items():
        value = size.get(field)
        if type(value) is not int or not 1 <= value <= limit:
            raise http_exc.BadRequest(
                f'size.{field} must be an integer between 1 and {limit}.')
    return orb_model.Size(**{field: size[field] for field in limits})


def _public_key(key):
    if not isinstance(key, str):
        raise http_exc.BadRequest('public_key is required.')
    key = ssh.public_key(key)
    if key is None:
        raise http_exc.BadRequest(
            'public_key must be an OpenSSH public key.')
    return key


def _ssh_allowed_cidr(cidr):
    """The network the orb admits SSH from, normalized.

    Only the harness knows where it will connect from (docs/adr/0008).
    """
    if not isinstance(cidr, str) or not cidr:
        raise http_exc.BadRequest(
            'ssh_allowed_cidr is required: the network the orb admits SSH '
            'from.')
    try:
        network = ipaddress.IPv4Network(cidr)
    except ValueError as e:
        # The orb's network and floating IP are IPv4 only: an IPv6 rule
        # would admit nobody.
        raise http_exc.BadRequest(
            f'ssh_allowed_cidr is not an IPv4 network: {e}') from e
    if network.prefixlen == 0:
        raise http_exc.BadRequest(
            'ssh_allowed_cidr cannot admit the whole Internet.')
    cap = CONF.orbs.ssh_allowed_cidr
    if cap is not None and not network.subnet_of(ipaddress.IPv4Network(cap)):
        raise http_exc.BadRequest(f'ssh_allowed_cidr must be inside {cap}.')
    return str(network)


def _image(image):
    image = image if image is not None else CONF.orbs.default_image
    if not isinstance(image, str) or not image:
        raise http_exc.BadRequest('image is required: no default image '
                                  'is configured.')
    if len(image) > _MAX_IMAGE_LENGTH:
        raise http_exc.BadRequest(
            f'image exceeds {_MAX_IMAGE_LENGTH} characters.')
    return image


def _view(observed):
    orb = observed.orb
    return {
        'id': orb.id,
        'status': orb.status.value,
        'size': {'vcpus': orb.size.vcpus,
                 'memory_mb': orb.size.memory_mb,
                 'disk_gb': orb.size.disk_gb},
        'image': orb.image,
        'ssh_host': observed.ssh_host,
        'ssh_host_keys': (list(orb.ssh_host_keys)
                          if orb.ssh_host_keys is not None else None),
        'ssh_user': CONF.orbs.ssh_users.get(orb.image,
                                            CONF.orbs.default_ssh_user),
        'ssh_allowed_cidr': orb.ssh_allowed_cidr,
        'fault': orb.fault,
        'created_at': orb.created_at.isoformat(),
    }
