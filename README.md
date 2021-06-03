# sider

[![tox](https://github.com/eirikrye/sider/actions/workflows/python_test.yml/badge.svg)](https://github.com/eirikrye/sider/actions/workflows/python_test.yml)

The fastest asyncio redis client library that you probably shouldn't use.

## examples

### basic usage

```python
import asyncio

from sider import RedisClient


async def main():
    client = await RedisClient().connect()
    await client.set("hello", "world")
    value = await client.get("hello")
    print(value)


if __name__ == "__main__":
    asyncio.run(main())
```

### (very) fast pipelining

```python
import asyncio

from sider import RedisClient


async def main():
    client = await RedisClient().connect()

    # create a bunch of items
    items = [str(n) for n in range(10_000)]

    # set a bunch of items
    with client.pipeline() as p:
        for item in items:
            p.command("SET", item, item)
        results = await p.execute(ignore_results=True)

    # read back a bunch of items
    with client.pipeline() as p:
        for item in items:
            p.command("GET", item)
        results = await p.execute()

    assert results == items


if __name__ == "__main__":
    asyncio.run(main())
```

### connection pool

```python
import asyncio
import random

from sider import RedisPool


async def main() -> None:
    pool = RedisPool(size=2)

    async def pool_consumer(n: int) -> None:
        async with pool.acquire() as c:
            await c.set(f"key-{n+1}", f"val-{n+1}")
            assert await c.get(f"key-{n+1}") == f"val-{n+1}"
            await asyncio.sleep(random.random())
        print(f"pool consumer {n+1} complete")

    await asyncio.gather(*[pool_consumer(n) for n in range(8)])

    await pool.drain()


if __name__ == "__main__":
    asyncio.run(main())
```

### benchmark

according to this (informal) benchmark, sider's performance remains consistent while aioredis' performance degrades significantly as the number of commands in the pipeline/transaction grows.

```shell
% pip3 freeze | egrep '^(aredis|aioredis)'
aioredis==1.3.1
aredis==1.1.8
% python3 examples/multi_bench.py
[aioredis pipeline   ] 100 iterations, 23.8µs/it, total: 2.4ms
[aioredis transaction] 100 iterations, 24.6µs/it, total: 2.5ms
[aredis pipeline     ] 100 iterations, 18.7µs/it, total: 1.9ms
[aredis transaction  ] 100 iterations, 10.2µs/it, total: 1.0ms
[sider pipeline      ] 100 iterations, 5.8µs/it, total: 0.6ms
[sider transaction   ] 100 iterations, 7.6µs/it, total: 0.8ms

[aioredis pipeline   ] 1000 iterations, 17.6µs/it, total: 17.6ms
[aioredis transaction] 1000 iterations, 23.0µs/it, total: 23.0ms
[aredis pipeline     ] 1000 iterations, 9.5µs/it, total: 9.5ms
[aredis transaction  ] 1000 iterations, 9.7µs/it, total: 9.7ms
[sider pipeline      ] 1000 iterations, 3.3µs/it, total: 3.3ms
[sider transaction   ] 1000 iterations, 4.1µs/it, total: 4.1ms

[aioredis pipeline   ] 10000 iterations, 24.8µs/it, total: 248.2ms
[aioredis transaction] 10000 iterations, 80.2µs/it, total: 801.6ms
[aredis pipeline     ] 10000 iterations, 8.0µs/it, total: 80.2ms
[aredis transaction  ] 10000 iterations, 8.0µs/it, total: 80.1ms
[sider pipeline      ] 10000 iterations, 2.8µs/it, total: 27.6ms
[sider transaction   ] 10000 iterations, 3.3µs/it, total: 33.4ms

[aioredis pipeline   ] 40000 iterations, 31.0µs/it, total: 1241.0ms
[aioredis transaction] 40000 iterations, 266.2µs/it, total: 10647.4ms
[aredis pipeline     ] 40000 iterations, 7.9µs/it, total: 315.9ms
[aredis transaction  ] 40000 iterations, 7.5µs/it, total: 300.0ms
[sider pipeline      ] 40000 iterations, 2.7µs/it, total: 106.6ms
[sider transaction   ] 40000 iterations, 3.3µs/it, total: 132.4ms
```
