import asyncio

from sider import RedisClient


async def test_client():
    client = await RedisClient().connect()

    print(await client.hset("dude", {"bro": "man"}))


if __name__ == "__main__":
    asyncio.run(test_client())
