"""Le risorse HTTP di /v1. Il contratto e in docs/design/api.md."""

import base64
import binascii

import flask
from werkzeug import exceptions as http_exc

from orbit import clients
from orbit.conf import CONF
from orbit import orb as orb_model
from orbit import service

blueprint = flask.Blueprint('v1', __name__)

_KEY_TYPES = ('ssh-ed25519', 'ssh-rsa', 'ecdsa-sha2-nistp256',
              'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521',
              'sk-ssh-ed25519@openssh.com',
              'sk-ecdsa-sha2-nistp256@openssh.com')


def _orbs():
    return flask.current_app.config['ORBS']


def _context():
    environ = flask.request.environ
    project_id = environ.get('HTTP_X_PROJECT_ID')
    if not project_id:
        raise http_exc.Forbidden('Serve un token con ambito di progetto.')
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
            raise http_exc.BadRequest(f'Stato sconosciuto: {status}')
    return {'orbs': [_view(o) for o in _orbs().list(_context(), status)]}


@blueprint.get('/orbs/<orb_id>')
def show_orb(orb_id):
    observed = _orbs().get(_context(), orb_id)
    if observed is None:
        raise http_exc.NotFound(f'Orb {orb_id} non trovato.')
    return _view(observed)


@blueprint.errorhandler(clients.CapacityExhausted)
def _capacity_exhausted(error):
    return _error(409, 'Capacita esaurita: nessun host ha posto per la '
                       'taglia chiesta.')


@blueprint.errorhandler(clients.Unavailable)
def _unavailable(error):
    return _error(503, f'Servizio non raggiungibile: {error}')


@blueprint.errorhandler(http_exc.HTTPException)
def _http_error(error):
    return _error(error.code, error.description)


def _error(code, message):
    return {'error': {'code': code, 'message': message}}, code


def _create_request(body):
    if not isinstance(body, dict):
        raise http_exc.BadRequest('Il corpo deve essere un oggetto JSON.')
    return service.CreateRequest(
        size=_size(body.get('size')),
        public_key=_public_key(body.get('public_key')),
        image=_image(body.get('image')),
    )


def _size(size):
    if not isinstance(size, dict):
        raise http_exc.BadRequest(
            'size deve indicare vcpus, memory_mb e disk_gb.')
    limits = {'vcpus': CONF.orbs.max_vcpus,
              'memory_mb': CONF.orbs.max_memory_mb,
              'disk_gb': CONF.orbs.max_disk_gb}
    for field, limit in limits.items():
        value = size.get(field)
        if type(value) is not int or not 1 <= value <= limit:
            raise http_exc.BadRequest(
                f'size.{field} deve essere un intero fra 1 e {limit}.')
    return orb_model.Size(**{field: size[field] for field in limits})


def _public_key(key):
    if not isinstance(key, str):
        raise http_exc.BadRequest('public_key e obbligatoria.')
    parts = key.split()
    if len(parts) < 2 or parts[0] not in _KEY_TYPES:
        raise http_exc.BadRequest(
            'public_key deve essere una chiave pubblica OpenSSH.')
    try:
        base64.b64decode(parts[1], validate=True)
    except binascii.Error:
        raise http_exc.BadRequest(
            'public_key deve essere una chiave pubblica OpenSSH.')
    return key.strip()


def _image(image):
    image = image if image is not None else CONF.orbs.default_image
    if not isinstance(image, str) or not image:
        raise http_exc.BadRequest('image e obbligatoria: nessuna immagine '
                                  'predefinita e configurata.')
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
        'ssh_user': CONF.orbs.ssh_users.get(orb.image,
                                            CONF.orbs.default_ssh_user),
        'fault': orb.fault,
        'created_at': orb.created_at.isoformat(),
    }
