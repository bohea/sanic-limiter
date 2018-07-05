# demo start
from sanic import Sanic, Blueprint
from sanic.response import text

from sanic_limiter import Limiter, get_remote_address

app = Sanic(__name__)
limiter = Limiter(app, global_limits=['1 per hour', '10 per day'], key_func=get_remote_address)
bp = Blueprint('some_bp')
limiter.limit("2 per hour")(bp)


@bp.route("/bp1")
async def bp_t1(request):
    return text("bp_t1")


@app.route("/t1")
@limiter.limit("100 per hour;10/minute")
async def t1(request):
    return text("t1")


@app.route("/t2")
async def t2(request):
    return text("t2")


@app.route("/t3")
@limiter.exempt
async def t3(request):
    return text("t3")

@app.route("/t4/<part>")
@limiter.limit("1/minute")
async def t1(request, part):
    return text(part)

app.blueprint(bp)

app.run(host="0.0.0.0", port=5000, debug=True)
# demo end

import unittest

class DemoTest(unittest.TestCase):

    def test_demo(self):
        self.assertEqual(app.test_client.get('/t1')[1].body.decode(), 't1')
        self.assertEqual(app.test_client.get('/t1')[1].status, 200)
        self.assertEqual(app.test_client.get('/t1')[1].status, 200)
        self.assertEqual(app.test_client.get('/t2')[1].status, 200)
        self.assertEqual(app.test_client.get('/t2')[1].status, 429)
        self.assertEqual(app.test_client.get('/t3')[1].status, 200)
        self.assertEqual(app.test_client.get('/t3')[1].status, 200)
        self.assertEqual(app.test_client.get('/t4/one')[1].status, 200)
        self.assertEqual(app.test_client.get('/t4/two')[1].status, 429)
        self.assertEqual(app.test_client.get('/bp1')[1].status, 200)
        self.assertEqual(app.test_client.get('/bp1')[1].status, 200)
        self.assertEqual(app.test_client.get('/bp1')[1].status, 429)
