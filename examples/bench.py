import asyncio
import sys
from contextlib import asynccontextmanager

import aioredis
from aredis import StrictRedis
from sider import RedisClient
from sider.utils import time_it

if sys.platform != "win32":
    import uvloop

    uvloop.install()


@asynccontextmanager
async def get_aioredis():
    redis = await aioredis.create_redis("redis://localhost")
    yield redis
    redis.close()
    await redis.wait_closed()


@asynccontextmanager
async def get_sider():
    redis = await RedisClient("localhost").connect()
    yield redis
    await redis.close()


@asynccontextmanager
async def get_aredis():
    redis = StrictRedis("localhost")
    yield redis


async def main():

    iterations = 400000
    keys = [b"%d" % n for n in range(iterations)]
    str_keys = ["%d" % n for n in range(iterations)]

    print("---")

    async with get_sider() as r:

        async def check_and_flush():
            assert await r.command("DBSIZE") == iterations
            await r.command("FLUSHDB")
            assert await r.command("DBSIZE") == 0

        async def check_result():
            check_value = b"OK" if not r._encoding else "OK"
            assert len(res) == iterations
            for v in res:
                assert v == check_value
            await check_and_flush()

        await r.command("FLUSHDB")
        assert await r.command("DBSIZE") == 0

        with time_it("sider pipe (str)", iterations=iterations):
            with r.pipeline() as p:
                for k in str_keys:
                    p.command("SET", k, k)
                res = await p.execute()

        await check_result()

        with time_it("sider pipe (bytes)", iterations=iterations):
            with r.pipeline() as p:
                for k in keys:
                    p.bytes_command(b"SET", k, k)
                res = await p.execute()

        await check_result()

        with time_it("sider transaction (str)", iterations=iterations):
            with r.pipeline() as p:
                for k in str_keys:
                    p.command("SET", k, k)
                res = await p.execute(transaction=True)

        await check_result()

        with time_it("sider transaction (bytes)", iterations=iterations):
            with r.pipeline() as p:
                for k in keys:
                    p.bytes_command(b"SET", k, k)
                res = await p.execute(transaction=True)

        await check_result()

        with time_it("sider pipe ignore (str)", iterations=iterations):
            p = r.pipeline()
            for k in str_keys:
                p.command("SET", k, k)
            res = await p.execute(ignore_results=True)

        assert res == None
        await check_and_flush()

        with time_it("sider pipe ignore (bytes)", iterations=iterations):
            p = r.pipeline()
            for k in keys:
                p.bytes_command(b"SET", k, k)
            res = await p.execute(ignore_results=True)

        assert res == None
        await check_and_flush()

    # print("---")

    # async with get_aredis() as r:
    #     # with time_it("aredis set", iterations=iterations):
    #     #     for n in range(iterations):
    #     #         await r.set(k, k)
    #     # with time_it("aredis get", iterations=iterations):
    #     #     for n in range(iterations):
    #     #         await r.get(k)
    #     with time_it("aredis   pipeline    ", iterations=iterations):
    #         async with await r.pipeline(transaction=False) as p:
    #             for k in keys:
    #                 await p.set(k, k)
    #             res = await p.execute()

    #     assert len(res) == iterations
    #     for v in res:
    #         assert v

    #     with time_it("aredis   transaction ", iterations=iterations):
    #         async with await r.pipeline(transaction=True) as p:
    #             for k in keys:
    #                 await p.set(k, k)
    #             res = await p.execute()

    #     assert len(res) == iterations
    #     for v in res:
    #         assert v


asyncio.run(main())
