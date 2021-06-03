class RedisError(Exception):
    pass


class ClientError(RedisError):
    pass


class ProtocolError(RedisError):
    pass


class ReplyError(RedisError):
    pass
