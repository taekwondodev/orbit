import unittest

from werkzeug import test as werkzeug_test

from orbit.api import app
from orbit import conf


class TestAuthentication(unittest.TestCase):

    def setUp(self):
        conf.CONF([], project='orbit', default_config_files=[])
        self.addCleanup(conf.CONF.reset)
        conf.CONF.set_override('www_authenticate_uri',
                               'http://keystone.invalid/identity',
                               'keystone_authtoken')
        conf.CONF.set_override('connection', 'sqlite://', 'database')

    def test_request_without_token_is_rejected(self):
        client = werkzeug_test.Client(app.create_wsgi_app())

        response = client.get('/v1/orbs')

        self.assertEqual(401, response.status_code)
        self.assertIn('keystone.invalid',
                      response.headers['WWW-Authenticate'])
