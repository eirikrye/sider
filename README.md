# sider

[![tox](https://github.com/eirikrye/sider/actions/workflows/python_test.yml/badge.svg)](https://github.com/eirikrye/sider/actions/workflows/python_test.yml)

The fastest asyncio redis client library you (probably) shouldn't use.

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
            await c.set("hello", "world")
            await asyncio.sleep(random.random())
        print(f"pool consumer {n+1} complete")

    await asyncio.gather(*[pool_consumer(n) for n in range(8)])

    await pool.drain()


if __name__ == "__main__":
    asyncio.run(main())
```
