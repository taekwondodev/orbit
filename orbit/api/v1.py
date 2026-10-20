"""Le risorse HTTP di /v1. Il contratto e in docs/design/api.md."""

import flask

blueprint = flask.Blueprint('v1', __name__)


@blueprint.get('/orbs')
def list_orbs():
    return {'orbs': []}
