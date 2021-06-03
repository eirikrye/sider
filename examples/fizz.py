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
