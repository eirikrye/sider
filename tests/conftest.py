import os

import pytest

from sider import RedisClient, RedisPool

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))


@pytest.fixture
async def redis():
    client = RedisClient(host=REDIS_HOST, port=REDIS_PORT)
    client = await client.connect()
    assert await client.command("FLUSHALL") == "OK"
    yield client
    assert await client.command("FLUSHALL") == "OK"
    await client.close()


@pytest.fixture
async def redis_pool():
    pool = RedisPool(host=REDIS_HOST, port=REDIS_PORT, size=4)
    yield pool
    assert await pool.drain() is None
