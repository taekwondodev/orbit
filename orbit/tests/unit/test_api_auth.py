import tempfile
import unittest

from oslo_db.sqlalchemy import enginefacade
import sqlalchemy as sa
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

    def test_api_creates_its_table_and_starts_again_with_it(self):
        app.create_wsgi_app()
        app.create_wsgi_app()

        engine = enginefacade.writer.get_engine()
        self.assertIn('orbs', sa.inspect(engine).get_table_names())

    def test_api_does_not_start_with_an_invalid_ssh_cap(self):
        for cap in ('harness', '198.51.100.20/24', '2001:db8::/32'):
            with self.subTest(cap=cap):
                conf.CONF.set_override('ssh_allowed_cidr', cap, 'orbs')

                with self.assertRaisesRegex(conf.InvalidOption,
                                            'ssh_allowed_cidr'):
                    app.create_wsgi_app()

    def test_api_does_not_start_with_a_minimum_prefix_out_of_range(self):
        with tempfile.NamedTemporaryFile('w', suffix='.conf') as config:
            config.write('[orbs]\nssh_min_prefix = 0\n')
            config.flush()
            conf.CONF([], project='orbit', default_config_files=[config.name])

            with self.assertRaisesRegex(conf.InvalidOption, 'ssh_min_prefix'):
                app.create_wsgi_app()

    def test_api_does_not_start_without_time_to_boot(self):
        for ready_timeout in (60, 120):
            with self.subTest(ready_timeout=ready_timeout):
                conf.CONF.set_override('ready_timeout', ready_timeout,
                                       'orbs')

                with self.assertRaisesRegex(conf.InvalidOption,
                                            'ready_timeout'):
                    app.create_wsgi_app()
