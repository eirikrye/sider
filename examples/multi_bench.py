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

    print(
        f"[{name[:20]:20}] {iterations} iterations, {elapsed / iterations / 1000:.1f}µs/it, total: {elapsed * 1e-6:.1f}ms"
    )


async def bench_redis(iterations: int):
    from redis.asyncio import Redis

    redis = Redis(encoding="utf-8", decode_responses=True)
    await redis.flushdb()

    with time_it("redis pipeline", iterations):
        tr = redis.pipeline()
        for _ in range(iterations):
            tr.set("foo", "bar")
        tr.get("foo")
        res = await tr.execute()
    assert len(res) == iterations + 1
    assert res[-1] == "bar"

    with time_it("redis transaction", iterations):
        tr = redis.pipeline(transaction=True)
        for _ in range(iterations):
            tr.set("foo", "bar")
        tr.get("foo")
        res = await tr.execute()
    assert len(res) == iterations + 1
    assert res[-1] == "bar"

    await redis.aclose()


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
    for iterations in [100, 1000, 10000, 100000, 500000]:
        await bench_redis(iterations)
        await bench_sider(iterations)
        print()


asyncio.run(main())
