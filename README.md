# Sanic-Limiter
A rate limiting extension inspired by flask-limiter
Provides rate limiting features for Sanic. Supports  in-memory, redis and memcache as storage.

Quickstart
===========
a demo for quickstart:

```
from sanic import Sanic
from sanic.response import text

from sanic_limiter import Limiter

app = Sanic(__name__)
limiter = Limiter(app, global_limits=['1 per hour', '10 per day'])


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

app.run(host="0.0.0.0", port=5000, debug=True)
```




