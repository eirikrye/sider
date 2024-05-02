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

according to this (informal) benchmark, sider's performance remains consistent while aioredis' performance degrades somewhat as the number of commands in the pipeline/transaction increases.

```shell
% pip3 freeze | grep redis
hiredis==2.3.2
redis==5.0.4
% python3 examples/multi_bench.py
[redis pipeline      ] 100 iterations, 6.7µs/it, total: 0.7ms
[redis transaction   ] 100 iterations, 6.5µs/it, total: 0.6ms
[sider pipeline      ] 100 iterations, 4.6µs/it, total: 0.5ms
[sider transaction   ] 100 iterations, 4.8µs/it, total: 0.5ms

[redis pipeline      ] 1000 iterations, 5.8µs/it, total: 5.8ms
[redis transaction   ] 1000 iterations, 4.3µs/it, total: 4.3ms
[sider pipeline      ] 1000 iterations, 1.9µs/it, total: 1.9ms
[sider transaction   ] 1000 iterations, 2.4µs/it, total: 2.4ms

[redis pipeline      ] 10000 iterations, 4.2µs/it, total: 42.4ms
[redis transaction   ] 10000 iterations, 4.2µs/it, total: 41.7ms
[sider pipeline      ] 10000 iterations, 2.3µs/it, total: 23.4ms
[sider transaction   ] 10000 iterations, 2.0µs/it, total: 20.0ms

[redis pipeline      ] 100000 iterations, 4.2µs/it, total: 419.2ms
[redis transaction   ] 100000 iterations, 3.9µs/it, total: 385.9ms
[sider pipeline      ] 100000 iterations, 1.6µs/it, total: 158.6ms
[sider transaction   ] 100000 iterations, 1.8µs/it, total: 180.4ms

[redis pipeline      ] 500000 iterations, 4.1µs/it, total: 2050.1ms
[redis transaction   ] 500000 iterations, 4.0µs/it, total: 2019.4ms
[sider pipeline      ] 500000 iterations, 1.4µs/it, total: 721.6ms
[sider transaction   ] 500000 iterations, 2.2µs/it, total: 1087.4ms
```
