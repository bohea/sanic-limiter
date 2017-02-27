"""
the sanic extension
"""

from functools import wraps, partial
import logging
import six
import sys
import inspect

from limits.errors import ConfigurationError
from limits.storage import storage_from_string
from limits.strategies import STRATEGIES
from limits.util import parse_many

from .errors import RateLimitExceeded
from .util import get_remote_address


class C:
    ENABLED = "RATELIMIT_ENABLED"
    STORAGE_URL = "RATELIMIT_STORAGE_URL"
    STORAGE_OPTIONS = "RATELIMIT_STORAGE_OPTIONS"
    STRATEGY = "RATELIMIT_STRATEGY"
    GLOBAL_LIMITS = "RATELIMIT_GLOBAL"
    SWALLOW_ERRORS = "RATELIMIT_SWALLOW_ERRORS"


class ExtLimit(object):
    """
    simple wrapper to encapsulate limits and their context
    """

    def __init__(self, limit, key_func, scope, per_method, methods, error_message,
                 exempt_when):
        self._limit = limit
        self.key_func = key_func
        self._scope = scope
        self.per_method = per_method
        self.methods = methods and [m.lower() for m in methods] or methods
        self.error_message = error_message
        self.exempt_when = exempt_when

    @property
    def limit(self):
        return self._limit() if callable(self._limit) else self._limit

    @property
    def scope(self):
        return self._scope

    @property
    def is_exempt(self):
        """Check if the limit is exempt."""
        return self.exempt_when and self.exempt_when()


class Limiter(object):
    """
    :param app: :class:`sanic.Sanic` instance to initialize the extension with.
    :param list global_limits: a variable list of strings denoting global
     limits to apply to all routes. :ref:`ratelimit-string` for  more details.
    :param function key_func: a callable that returns the key to rate limit by.
    :param str strategy: the strategy to use. refer to :ref:`ratelimit-strategy`
    :param str storage_uri: the storage location. refer to :ref:`ratelimit-conf`
    :param dict storage_options: kwargs to pass to the storage implementation upon instantiation.
    :param bool swallow_errors: whether to swallow errors when hitting a rate limit.
     An exception will still be logged. default ``False``
    """

    def __init__(self, app=None
                 , key_func=None
                 , global_limits=[]
                 , strategy=None
                 , storage_uri=None
                 , storage_options={}
                 , swallow_errors=False
                 ):
        self.app = app
        self.logger = logging.getLogger("sanic-limiter")

        self.enabled = True
        self._global_limits = []
        self._exempt_routes = set()
        self._request_filters = []
        self._strategy = strategy
        self._storage_uri = storage_uri
        self._storage_options = storage_options
        self._swallow_errors = swallow_errors
        self._key_func = key_func or get_remote_address
        for limit in global_limits:
            self._global_limits.extend(
                [
                    ExtLimit(
                        limit, self._key_func, None, False, None, None, None
                    ) for limit in parse_many(limit)
                    ]
            )
        self._route_limits = {}
        self._dynamic_route_limits = {}
        self._storage = None
        self._limiter = None
        self._storage_dead = False

        class BlackHoleHandler(logging.StreamHandler):
            def emit(*_):
                return

        self.logger.addHandler(BlackHoleHandler())
        if app:
            self.init_app(app)

    def init_app(self, app):
        """
        :param app: :class:`sanic.Sanic` instance to rate limit.
        """
        self.enabled = app.config.setdefault(C.ENABLED, True)
        self._swallow_errors = app.config.setdefault(
            C.SWALLOW_ERRORS, self._swallow_errors
        )
        self._storage_options.update(
            app.config.get(C.STORAGE_OPTIONS, {})
        )
        self._storage = storage_from_string(
            self._storage_uri
            or app.config.setdefault(C.STORAGE_URL, 'memory://'),
            **self._storage_options
        )
        strategy = (
            self._strategy
            or app.config.setdefault(C.STRATEGY, 'fixed-window')
        )
        if strategy not in STRATEGIES:
            raise ConfigurationError("Invalid rate limiting strategy %s" % strategy)
        self._limiter = STRATEGIES[strategy](self._storage)

        conf_limits = app.config.get(C.GLOBAL_LIMITS, None)
        if not self._global_limits and conf_limits:
            self._global_limits = [
                ExtLimit(
                    limit, self._key_func, None, False, None, None, None
                ) for limit in parse_many(conf_limits)
                ]
        app.request_middleware.append(self.__check_request_limit)

    @property
    def limiter(self):
        return self._limiter

    def __check_request_limit(self, request):
        endpoint = request.url or ""
        view_handler = self.app.router.routes_static.get(endpoint, None)
        if view_handler is None:
            return
        view_func = view_handler.handler
        name = ("{}.{}".format(view_func.__module__, view_func.__name__) if view_func else "")
        if (not endpoint
            or not self.enabled
            or name in self._exempt_routes
            or any(fn() for fn in self._request_filters)
            ):
            return
        limits = self._route_limits.get(name, [])
        dynamic_limits = []
        if name in self._dynamic_route_limits:
            for lim in self._dynamic_route_limits[name]:
                try:
                    dynamic_limits.extend(
                        ExtLimit(
                            limit, lim.key_func, lim.scope, lim.per_method,
                            lim.methods, lim.error_message, lim.exempt_when
                        ) for limit in parse_many(lim.limit)
                    )
                except ValueError as e:
                    self.logger.error(
                        "failed to load ratelimit for view function %s (%s)"
                        , name, e
                    )
        failed_limit = None
        try:
            all_limits = []
            if not all_limits:
                all_limits = (limits + dynamic_limits or self._global_limits)
            for lim in all_limits:
                limit_scope = lim.scope or endpoint
                if lim.is_exempt:
                    return
                if lim.methods is not None and request.method.lower() not in lim.methods:
                    return
                if lim.per_method:
                    limit_scope += ":%s" % request.method
                key_func_argvs = list(inspect.signature(lim.key_func).parameters.keys())
                if key_func_argvs and key_func_argvs[0] == 'request':
                    key_func_callable = partial(lim.key_func, request)
                else:
                    key_func_callable = lim.key_func
                if not self.limiter.hit(lim.limit, key_func_callable(), limit_scope):
                    self.logger.warning(
                        "ratelimit %s (%s) exceeded at endpoint: %s"
                        , lim.limit, key_func_callable(), limit_scope
                    )
                    failed_limit = lim
                    break

            if failed_limit:
                if failed_limit.error_message:
                    exc_description = failed_limit.error_message if not callable(
                        failed_limit.error_message
                    ) else failed_limit.error_message()
                else:
                    exc_description = six.text_type(failed_limit.limit)
                raise RateLimitExceeded(exc_description)
        except Exception as e:  # no qa
            if isinstance(e, RateLimitExceeded):
                six.reraise(*sys.exc_info())
            if self._swallow_errors:
                self.logger.exception(
                    "Failed to rate limit. Swallowing error"
                )
            else:
                six.reraise(*sys.exc_info())

    def __limit_decorator(self, limit_value,
                          key_func=None, shared=False,
                          scope=None,
                          per_method=False,
                          methods=None,
                          error_message=None,
                          exempt_when=None):
        _scope = scope if shared else None

        def _inner(obj):
            func = key_func or self._key_func
            name = "{}.{}".format(obj.__module__, obj.__name__)
            dynamic_limit, static_limits = None, []
            if callable(limit_value):
                dynamic_limit = ExtLimit(limit_value, func, _scope, per_method,
                                         methods, error_message, exempt_when)
            else:
                try:
                    static_limits = [ExtLimit(
                        limit, func, _scope, per_method,
                        methods, error_message, exempt_when
                    ) for limit in parse_many(limit_value)]
                except ValueError as e:
                    self.logger.error("failed to configure {} {} ({})".format("view function", name, e))

            @wraps(obj)
            def __inner(*a, **k):
                return obj(*a, **k)

            if dynamic_limit:
                self._dynamic_route_limits.setdefault(name, []).append(
                    dynamic_limit
                )
            else:
                self._route_limits.setdefault(name, []).extend(
                    static_limits
                )
            return __inner

        return _inner

    def limit(self, limit_value, key_func=None, per_method=False,
              methods=None, error_message=None, exempt_when=None):
        """
        decorator to be used for rate limiting individual routes.

        :param limit_value: rate limit string or a callable that returns a string.
         :ref:`ratelimit-string` for more details.
        :param function key_func: function/lambda to extract the unique identifier for
         the rate limit. defaults to remote address of the request.
        :param bool per_method: whether the limit is sub categorized into the http
         method of the request.
        :param list methods: if specified, only the methods in this list will be rate
         limited (default: None).
        :param error_message: string (or callable that returns one) to override the
         error message used in the response.
        :return:
        """
        return self.__limit_decorator(limit_value, key_func, per_method=per_method,
                                      methods=methods, error_message=error_message,
                                      exempt_when=exempt_when)

    def shared_limit(self, limit_value, scope, key_func=None,
                     error_message=None, exempt_when=None):
        """
        decorator to be applied to multiple routes sharing the same rate limit.

        :param limit_value: rate limit string or a callable that returns a string.
         :ref:`ratelimit-string` for more details.
        :param scope: a string or callable that returns a string
         for defining the rate limiting scope.
        :param function key_func: function/lambda to extract the unique identifier for
         the rate limit. defaults to remote address of the request.
        :param error_message: string (or callable that returns one) to override the
         error message used in the response.
        """
        return self.__limit_decorator(
            limit_value, key_func, True, scope, error_message=error_message,
            exempt_when=exempt_when
        )

    def exempt(self, obj):
        """
        decorator to mark a view as exempt from global rate limits.
        """
        name = "{}.{}".format(obj.__module__, obj.__name__)

        @wraps(obj)
        def __inner(*a, **k):
            return obj(*a, **k)

        self._exempt_routes.add(name)
        return __inner

    def request_filter(self, fn):
        """
        decorator to mark a function as a filter to be executed
        to check if the request is exempt from rate limiting.
        """
        self._request_filters.append(fn)
        return fn

    def reset(self):
        """
        resets the storage if it supports being reset
        """
        try:
            self._storage.reset()
            self.logger.info("Storage has been reset and all limits cleared")
        except NotImplementedError:
            self.logger.warning("This storage type does not support being reset")
