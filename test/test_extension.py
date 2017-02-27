import unittest
from unittest import mock
import logging

from limits.strategies import MovingWindowRateLimiter
from limits.storage import MemoryStorage
from sanic import Sanic
from sanic.response import text

from sanic_limiter.util import get_remote_address
from sanic_limiter import Limiter
from sanic_limiter.extension import C


class SanicLimiterTest(unittest.TestCase):

    def setUp(self):
        return

    def build_app(self, config={}, **limiter_args):
        app = Sanic(__name__)
        for k, v in config.items():
            app.config.setdefault(k, v)
        limiter_args.setdefault('key_func', get_remote_address)
        limiter = Limiter(app, **limiter_args)
        mock_handler = mock.Mock()
        mock_handler.level = logging.INFO
        limiter.logger.addHandler(mock_handler)
        return app, limiter

    def test_config_limiter(self):
        app_config = {C.ENABLED: False, C.SWALLOW_ERRORS: True, C.STORAGE_URL: 'redis://localhost:6379/0',
                      C.STRATEGY: 'fixed-window-elastic-expiry'}
        app, limiter = self.build_app(config=app_config, key_func=get_remote_address, strategy='moving-window',
                                      storage_uri='memory://')
        self.assertEqual(isinstance(limiter.limiter, MovingWindowRateLimiter), True)
        self.assertEqual(isinstance(limiter._storage, MemoryStorage), True)
        self.assertEqual(limiter.enabled, False)
        self.assertEqual(limiter._swallow_errors, True)

    def test_limiter_response(self):
        app, limiter = self.build_app(config={}, global_limits=['1/day'])

        @app.route("/t1")
        async def t1(request):
            return text("t1")

        app.test_client.get("/t1")
        request, response = app.test_client.get("/t1")
        self.assertTrue(response.status == 429 and '1 per 1 day' in response.body.decode())

    def test_combined_rate_limits(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS: "1 per hour; 10 per day"
        })

        @app.route("/t1")
        @limiter.limit("100 per hour;10/minute")
        async def t1(request):
            return text("t1")

        @app.route("/t2")
        async def t2(request):
            return text("t2")

        cli = app.test_client
        self.assertEqual(200, cli.get("/t1")[1].status)
        self.assertEqual(200, cli.get("/t1")[1].status)
        self.assertEqual(200, cli.get("/t2")[1].status)
        self.assertEqual(429, cli.get("/t2")[1].status)

    def test_multiple_decorators(self):
        app, limiter = self.build_app()

        def limit_condition1():
            return '1'

        def limit_condition2(request):
            return request.headers.get('X_FORWARDED_FOR', '127.0.0.1')

        @app.route("/t1")
        @limiter.limit("100 per minute", key_func=limit_condition1)  # limit for all users
        @limiter.limit("50/minute", key_func=limit_condition2)  # per ip as per default key_func
        async def t1(request):
            return text(t1)

        cli = app.test_client
        for i in range(0, 100):
            self.assertEqual(200 if i < 50 else 429, cli.get("/t1")[1].status)
        for i in range(50):
            self.assertEqual(200, cli.get("/t1", headers={'X_FORWARDED_FOR': '127.0.0.2'})[1].status)
        self.assertEqual(429, cli.get("/t1")[1].status)
        self.assertEqual(429, cli.get("/t1")[1].status)

    def test_exempt_routes(self):
        app, limiter = self.build_app(global_limits=["1/day"])

        @app.route("/t1")
        async def t1(request):
            return text("test")

        @app.route("/t2")
        @limiter.exempt
        async def t2(request):
            return text("test")

        cli = app.test_client
        self.assertEqual(cli.get("/t1")[1].status, 200)
        self.assertEqual(cli.get("/t1")[1].status, 429)
        self.assertEqual(cli.get("/t2")[1].status, 200)
        self.assertEqual(cli.get("/t2")[1].status, 200)

    def test_explicit_method_limits(self):
        app, limiter = self.build_app()

        @limiter.limit("1/second", methods=["GET"])
        @app.route("/t1", methods=["GET", "POST"])
        async def t1(request):
            return text("test")

        cli = app.test_client
        self.assertEqual(200, cli.get("/t1")[1].status)
        self.assertEqual(429, cli.get("/t1")[1].status)
        self.assertEqual(200, cli.post("/t1")[1].status)
        self.assertEqual(200, cli.post("/t1")[1].status)
