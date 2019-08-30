"""

"""


def get_remote_address(request):
    """
    :param: request: request object of sanic
    :return: the ip address of given request (or 127.0.0.1 if none found)
    """
    # Check if request object has remote_addr attribute set
    # Seems to break on sanic 19.6.3
    if hasattr(request, 'remote_addr'):
        return request.remote_addr
    else:
        return request.ip
