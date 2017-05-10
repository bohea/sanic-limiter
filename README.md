# Sanic-Limiter
A rate limiting extension inspired by flask-limiter
Provides rate limiting features for Sanic. Supports  in-memory, redis and memcache as storage based on alisaifee/limits.

Quickstart
===========
Demo for quickstart:

```python
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

app.blueprint(bp)

app.run(host="0.0.0.0", port=5000, debug=True)
```

Aboved demo provides:

* build Limiter instance with giving sanic app and global_limits;
* global_limits will be applied to all routes;
* /t1 has its own limit rules(using decorator provides by limiter.limit) which will bypass the global_limits;
* /t2 uses global_limits;
* /t3 will exempt from any global_limits;
* all the rate limits are based on get_remote_address, you can customize yours;
* when any rate limit is triggered, the view function will not be called and responses with http code 429;

Install
==============
```console
pip install sanic_limiter
```


Initialization
===================

There are two basic ways:

* constructor:

	```python
	from sanic_limiter import Limiter, get_remote_address

	limiter = Limiter(app, key_func=get_remote_address)
	```

* init_app:

	```python
	from sanic_limiter import Limiter, get_remote_address

	limiter = Limiter(key_func=get_remote_address)
	limiter.init_app(app)
	```

Key function
=========================
key function is customizable, an reasonable example is rate limiting by userid:

```python
def get_request_userid(request):
	return request.args.get('userid', '')

    @limiter.limit("50/minute", key_func=get_request_userid)
    async def t1(request):
    	return text(t1)
```
basicly, customized key function would like to access sanic request instance(not necessarily although), sanic request instance will be injected if key function has only one positional argument.


### Danger:

if key function has more than one positional argument, an exception will be rasied.


Rate limit string notation
================================

Rate limits are specified as strings following the format:

[count] [per|/] [n (optional)] [second|minute|hour|day|month|year]

You can combine multiple rate limits by separating them with a delimiter of your choice.

Examples:

* 10 per hour
* 10/hour
* 10/hour;100/day;2000 per year
* 100/day, 500/7days

Requirements:
==============================
* limits>=1.2.1  (<https://github.com/alisaifee/limits>)
* sanic>=0.4.0
* six>=1.4.1

References:
=====================
Flask-Limiter: <http://flask-limiter.readthedocs.io/en/stable/#keyfunc-customization>
