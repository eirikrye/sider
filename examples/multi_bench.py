# pylint: disable=import-outside-toplevel

import asyncio
import sys
import time
from contextlib import contextmanager

if sys.platform != "win32":
    import uvloop

    uvloop.install()


@contextmanager
def time_it(name: str, iterations: int):
    start = time.perf_counter_ns()
    yield None
    elapsed = time.perf_counter_ns() - start

    print(f"[{name[:20]:20}] {iterations} iterations, {elapsed / iterations / 1000:.1f}µs/it, total: {elapsed * 1e-6:.1f}ms")


async def bench_aioredis(iterations: int):
    import aioredis

    redis = await aioredis.create_redis_pool("redis://localhost")
    await redis.flushdb()

    with time_it("aioredis pipeline", iterations):
        tr = redis.pipeline()
        for _ in range(iterations):
            tr.set("foo", "bar")
        tr.get("foo", encoding="utf8")
        res = await tr.execute()
    assert len(res) == iterations + 1
    assert res[-1] == "bar"

    with time_it("aioredis transaction", iterations):
        tr = redis.multi_exec()
        for _ in range(iterations):
            tr.set("foo", "bar")
        tr.get("foo", encoding="utf8")
        res = await tr.execute()
    assert len(res) == iterations + 1
    assert res[-1] == "bar"

    redis.close()
    await redis.wait_closed()


async def bench_aredis(iterations: int):
    import aredis

    redis = aredis.StrictRedis("localhost", decode_responses=True)
    await redis.flushdb()

    with time_it("aredis pipeline", iterations):
        async with await redis.pipeline(transaction=False) as tr:
            for _ in range(iterations):
                await tr.set("foo", "bar")
            await tr.get("foo")
            res = await tr.execute()
    assert len(res) == iterations + 1
    assert res[-1] == "bar"

    with time_it("aredis transaction", iterations):
        async with await redis.pipeline(transaction=False) as tr:
            for _ in range(iterations):
                await tr.set("foo", "bar")
            await tr.get("foo")
            res = await tr.execute()
    assert len(res) == iterations + 1
    assert res[-1] == "bar"


async def bench_sider(iterations: int):
    import sider

    redis = await sider.RedisClient("localhost").connect()
    await redis.command("flushdb")

    with time_it("sider pipeline", iterations):
        tr = redis.pipeline()
        for _ in range(iterations):
            tr.command("set", "foo", "bar")
        tr.command("get", "foo")
        res = await tr.execute()
    assert len(res) == iterations + 1
    assert res[-1] == "bar"

    with time_it("sider transaction", iterations):
        tr = redis.pipeline()
        for _ in range(iterations):
            tr.command("set", "foo", "bar")
        tr.command("get", "foo")
        res = await tr.execute(
            transaction=True,
        )
    assert len(res) == iterations + 1
    assert res[-1] == "bar"

    await redis.close()


async def main():
    for iterations in [100, 1000, 10000, 40000]:
        await bench_aioredis(iterations)
        await bench_aredis(iterations)
        await bench_sider(iterations)
        print()


asyncio.run(main())
