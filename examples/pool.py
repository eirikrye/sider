import asyncio
import logging
import random

from sider import RedisPool

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)-15s] [%(name)s] [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


async def test_client() -> None:
    pool = RedisPool("127.0.0.1", 6379, size=4)

    async def pool_test(n: int) -> None:
        async with pool.acquire() as c:
            logger.debug("%d acquired, held: %d", n, pool.held)
            await c.set("hello", "world")
            await asyncio.sleep(random.random())

    await asyncio.gather(*[pool_test(n) for n in range(8)])

    await pool.drain()


if __name__ == "__main__":
    asyncio.run(test_client())
