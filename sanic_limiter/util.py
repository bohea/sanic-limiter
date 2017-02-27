"""

"""


def get_remote_address(request):
    """
    :param: request: request object of sanic
    :return: the ip address of given request (or 127.0.0.1 if none found)
    """
    return request.ip[0] or '127.0.0.1'
