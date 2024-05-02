# pylint: disable=protected-access

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from sider.client import ClientError, RedisClient, RedisError
from sider.exceptions import ReplyError
from sider.pool import RedisPool
from sider.utils import construct_command

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

proto_tests = [
    ((b"GET", b"foo"), b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n"),
    ((b"SET", b"bar", b"baz"), b"*3\r\n$3\r\nSET\r\n$3\r\nbar\r\n$3\r\nbaz\r\n"),
]


def test_construct_command():
    for args, expected in proto_tests:
        assert construct_command(*args) == expected


def test_mocked_writer():
    client = RedisClient()

    mock_writer = Mock()
    client._writer = mock_writer

    for args, expected in proto_tests:
        client._send_command(*args)
        mock_writer.write.assert_called_with(expected)


@pytest.mark.anyio
@pytest.mark.integration
async def test_keys_reads(redis, mocker):
    pipe = redis.pipeline()
    import random

    number = random.randint(500, 1000)

    for n in range(number):
        pipe.command("SET", f"aliases/{n}", str(n))
    await pipe.execute()
    spy = mocker.spy(redis._reader, "readuntil")
    pipe.command("KEYS", "aliases/*")
    result = await pipe.execute()
    assert len(result[0]) == number
    assert spy.call_count == 1


@pytest.mark.anyio
async def test_mocked_send_command():
    with patch("sider.RedisClient._send_command", new_callable=Mock) as mock_send:
        client = RedisClient()

        # mock the reader to emulate server
        mock_reader = AsyncMock()
        mock_reader.readuntil.return_value = b"$3\r\nbar\r\n"
        client._reader = mock_reader

        result = await client.get("foo")
        mock_send.assert_called_with(b"GET", b"foo")
        assert result == "bar"

        mock_reader.readuntil.return_value = b"$2\r\nOK\r\n"
        result = await client.set("bar", "baz")
        mock_send.assert_called_with(b"SET", b"bar", b"baz")
        assert result is None


# Integration tests require a running redis instance on 127.0.0.1:6379


@pytest.mark.anyio
async def test_sider_client():
    with pytest.raises(RedisError):
        await RedisClient(
            host=REDIS_HOST, port=REDIS_PORT, password="no-password"
        ).connect()

    client = RedisClient(
        host=REDIS_HOST, port=REDIS_PORT, database=1, name="sider-test"
    )
    await client.connect()

    assert await client.command("CLIENT", "GETNAME") == "sider-test"


@pytest.mark.anyio
async def test_sider_pool(redis_pool: RedisPool):
    assert redis_pool._size == 4
    assert redis_pool.available == 0

    client1 = await redis_pool.get()
    assert isinstance(client1, RedisClient)
    client2 = await redis_pool.get()
    assert redis_pool.held == 2
    assert redis_pool.available == 0

    await client2.close()
    await redis_pool.put(client1)
    await redis_pool.put(client2)
    assert redis_pool.available == 2
    assert redis_pool.held == 0

    # initialize the pool up to its max size
    await redis_pool.init()
    assert redis_pool.available == 4

    async with redis_pool.acquire() as redis:
        assert redis_pool.held == 1
        assert redis_pool.available == 3
        assert isinstance(redis, RedisClient)
        assert await redis.set("foo", "bar") is None
        assert await redis.get("foo") == "bar"

    # connection should be returned to the pool automatically

    assert redis_pool.held == 0
    assert redis_pool.available == 4

    # drain the pool, reducing the number of available clients to 0
    await redis_pool.drain(wait=True)
    assert redis_pool.available == 0
    assert redis_pool.held == 0

    # you should still be able to acquire new connections

    assert not redis_pool.locked

    client = await redis_pool.get()

    assert redis_pool.held == 1

    await redis_pool.put(client)

    assert redis_pool.available == 1


@pytest.mark.anyio
async def test_sider_sets(redis: RedisClient):
    set_items = [
        ("foo-set", ["foo", "bar", "baz"]),
        ("foo-set-2", ["foo", "bar", "baz", "plip", "plop"]),
    ]
    for key, members in set_items:
        assert await redis.sadd(key, *members) == len(members)
        assert await redis.smembers(key) == set(members)

    assert await redis.smembers("foo-set-nonexistant") == set()


@pytest.mark.anyio
async def test_sider_hashes(redis: RedisClient):
    hash_items = [
        ("foo-hash", {"foo": "bar", "baz": "qux"}),
        ("foo-hash-2", {"foo": "bar", "baz": "qux", "quux": "quuz"}),
    ]

    for key, item in hash_items:
        assert await redis.hset(key, item) == len(item.keys())
        assert await redis.hgetall(key) == item
        for k, v in item.items():
            assert await redis.hget(key, k) == v
        assert await redis.hkeys(key) == list(item.keys())
        assert await redis.hvals(key) == list(item.values())
        assert await redis.hlen(key) == len(item.keys())

        assert await redis.hmget(key, *item.keys()) == list(item.values())

    # try setting an existing key with a new dict, without overwriting/deleting previous fields

    new_dict = {"1": "2", "3": "4"}
    assert await redis.hset(hash_items[0][0], new_dict, overwrite=False) == len(
        new_dict.values()
    )
    assert await redis.hgetall(hash_items[0][0]) == dict(**new_dict, **hash_items[0][1])

    # then try overwriting it

    assert await redis.hset(hash_items[0][0], new_dict, overwrite=True) == len(
        new_dict.values()
    )
    assert await redis.hgetall(hash_items[0][0]) == new_dict

    # it's not possible to set empty hashes/dicts in redis
    with pytest.raises(ClientError):
        assert await redis.hset("foo-hash-empty", {})


@pytest.mark.anyio
async def test_sider_get(redis: RedisClient):
    # set keys
    assert await redis.set("foo", "bar") is None
    assert await redis.set("bar", "baz") is None

    # size of database should be 2
    assert await redis.command("DBSIZE") == 2

    # check that the keys are set, and values correct
    assert await redis.get("foo") == "bar"
    assert await redis.get("bar") == "baz"

    assert await redis.getset("qux", "foo") is None
    assert await redis.getset("qux", "bar") == "foo"
    assert await redis.getset("qux", "baz") == "bar"


@pytest.mark.anyio
async def test_sider_transaction(redis: RedisClient):
    assert await redis.multi() is None
    assert redis.in_multi

    # unable to nest multi
    with pytest.raises(AssertionError):
        await redis.multi()

    assert await redis.getset("foo", "bar") == "QUEUED"
    assert await redis.getset("foo", "baz") == "QUEUED"
    assert await redis.get("foo") == "QUEUED"
    assert await redis.execute() == [None, "bar", "baz"]
    assert not redis.in_multi

    async with redis.transaction():
        await redis.set("should-not-exist", "bar")
        assert redis.in_multi
    assert redis._last_sent == (b"DISCARD",)
    assert await redis.get("should-not-exist") is None
    assert not redis.in_multi

    async with redis.transaction():
        await redis.set("should-exist", "bar")
        await redis.execute()
    assert redis._last_sent == (b"EXEC",)
    assert await redis.get("should-exist") == "bar"
    assert not redis.in_multi


@pytest.mark.anyio
async def test_sider_connection(redis: RedisClient):
    assert await redis.ping() == "PONG"
    assert isinstance(await redis.ping(latency=True), int)

    # try connecting again
    with pytest.raises(ClientError):
        await redis.connect()


@pytest.mark.anyio
async def test_sider_generic(redis: RedisClient):
    await redis.set("foo", "bar")
    assert await redis.type("foo") == "string"
    await redis.sadd("foo-set", "bar")
    assert await redis.type("foo-set") == "set"

    with pytest.raises(RedisError):
        await redis.command("NONEXISTANT_COMMAND")

    assert redis._db == 0
    await redis.select(1)
    assert redis._db == 1
    await redis.select(0)
    await redis.select(0)

    assert await redis.ttl("foo-noexist") == -2
    await redis.set("foo-exist-nottl", "bar")
    assert await redis.ttl("foo-exist-nottl") == -1
    await redis.set("foo-exist-ttl", "bar", expire=50)
    assert await redis.ttl("foo-exist-ttl") == 50

    with pytest.raises(RedisError):
        await redis.command("SET", "too", "many", "arguments")


@pytest.mark.anyio
async def test_sider_swap(redis: RedisClient):
    # database out of range
    with pytest.raises(ReplyError):
        await redis.swap(database=100)

    await redis.set("foo", "bar")
    assert await redis.swap(database=1)
    assert redis.database == 0
    assert await redis.get("foo") is None

    await redis.set("foo-follow", "still-exists")
    assert await redis.swap(database=1, follow=True)
    assert redis.database == 1
    assert await redis.get("foo-follow") == "still-exists"


@pytest.mark.anyio
async def test_sider_pipeline(redis: RedisClient):
    pipe = redis.pipeline()
    pipe.command("SET", "foo", "bar")
    pipe.command("SET", "bar", "baz")
    pipe.command("GET", "foo")
    pipe.command("GET", "bar")
    assert await pipe.execute() == ["OK", "OK", "bar", "baz"]

    pipe.bytes_command(b"GET", b"foo")
    pipe.bytes_command(b"GET", b"bar")
    assert await pipe.execute() == ["bar", "baz"]

    # test pipeline with statement
    with redis.pipeline() as pipe:
        pipe.command("GET", "foo")
        assert await pipe.execute() == ["bar"]
        pipe.command("GET", "foo")
    # end of with statement should clear the pipeline buffer
    with pytest.raises(ClientError):
        await pipe.execute()

    await redis.multi()
    with pytest.raises(ClientError):
        pipe = redis.pipeline()
        pipe.command("PING")
        await pipe.execute()

    await redis.discard()

    # transaction pipeline

    with redis.pipeline() as pipe:
        pipe.command("GET", "foo")
        pipe.command("GET", "foo")
        assert (
            pipe._buffer
            == b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n"
        )
        assert await pipe.execute(transaction=True, ignore_results=True) is None
        assert pipe._buffer == b""
        assert redis._last_sent[0] == b"ECHO"

        pipe.command("GET", "foo")
        assert await pipe.execute(transaction=True) == ["bar"]
