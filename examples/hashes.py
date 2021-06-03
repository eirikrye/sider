import asyncio

from sider import RedisClient


async def main():
    client = await RedisClient().connect()

    await client.hset("sider-hash", {"hello": "world"})
    result = await client.hgetall("sider-hash")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
