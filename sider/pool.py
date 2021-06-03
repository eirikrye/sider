import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from .client import RedisClient

logger = logging.getLogger(__name__)


class RedisPool:
    __slots__ = (
        "host",
        "port",
        "name",
        "_size",
        "_password",
        "_held",
        "_lock",
        "_pool",
    )

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        password: Optional[str] = None,
        size: int = 1,
        name: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.name = name
        self._password = password
        self._held = 0
        self._size = size
        self._lock = asyncio.Lock()
        self._pool: "asyncio.Queue[RedisClient]" = asyncio.Queue(maxsize=size)

    async def init(self) -> "RedisPool":
        for _ in range(self._size - self.held - self.available):
            await self._pool.put(await self._get_client())
        return self

    async def _get_client(self) -> RedisClient:
        c = await RedisClient(self.host, self.port, self._password, name=self.name).connect()
        return c

    async def _ensure_open(self, conn: RedisClient) -> RedisClient:
        if conn.is_closed:
            logger.warning("Connection was closed.")
            conn = await self._get_client()
        return conn

    async def get(self) -> RedisClient:
        async with self._lock:
            if self._pool.empty() and self._held < self._size:
                conn = await self._get_client()
            else:
                conn = await self._ensure_open(await self._pool.get())
            self._held += 1
        return conn

    async def put(self, conn: RedisClient) -> None:
        assert not self._pool.full()
        await self._pool.put(await self._ensure_open(conn))
        self._held -= 1

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[RedisClient, None]:
        conn = await self.get()
        try:
            yield conn
        finally:
            await self.put(conn)

    async def drain(self, wait: bool = True) -> None:
        while not self._pool.empty() or (wait and self._held > 0):
            client = await self._pool.get()
            await client.close()
            logger.debug("drained %d", self._held)

    @property
    def held(self) -> int:
        return self._held

    @property
    def available(self) -> int:
        return self._pool.qsize()

    @property
    def locked(self) -> bool:
        return self._lock.locked()
