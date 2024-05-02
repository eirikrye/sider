import asyncio
import itertools
import logging
import secrets
import time
from contextlib import asynccontextmanager
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

import hiredis

from .exceptions import ClientError, ProtocolError, RedisError, ReplyError
from .utils import construct_command

logger = logging.getLogger(__name__)


class Pipeline:
    __slots__ = ("_client", "_buffer")

    def __init__(self, client: "RedisClient"):
        self._client = client
        self._buffer = bytearray()

    def __enter__(self) -> "Pipeline":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.clear()

    def command(self, *args: str) -> None:
        self._buffer += construct_command(*[arg.encode() for arg in args])

    def bytes_command(self, *args: bytes) -> None:
        self._buffer += construct_command(*args)

    def clear(self) -> None:
        self._buffer = bytearray()

    async def execute(
        self, transaction: bool = False, ignore_results: bool = False
    ) -> Any:
        buffer = self._buffer
        self.clear()
        return await self._client._buffer_execute(
            buffer, transaction=transaction, ignore_results=ignore_results
        )  # pylint: disable=protected-access


class RedisClient:
    __slots__ = (
        "_reader",
        "_writer",
        "_multi",
        "_parser",
        "_db",
        "_host",
        "_port",
        "_password",
        "_name",
        "_last_sent",
        "_encoding",
    )

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        password: Optional[str] = None,
        database: int = 0,
        name: Optional[str] = None,
        encoding: Optional[str] = "utf-8",
    ):
        self._host = host
        self._port = port
        self._password = password
        self._db = database
        self._name = name

        # io
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

        # modes
        self._multi = False
        self._last_sent: Optional[Tuple[bytes, ...]] = None

        self._encoding = encoding

        self._parser = hiredis.Reader(
            encoding=encoding,
            errors="strict",
            replyError=ReplyError,
            protocolError=ProtocolError,
        )

    async def connect(self) -> "RedisClient":
        if self._reader or self._writer:
            raise ClientError("Client is already connected.")

        (
            self._reader,
            self._writer,
        ) = await asyncio.open_connection(
            self._host,
            self._port,
            limit=1024 * 1024 * 1024,
        )
        if self._db != 0:
            await self.select(self._db)
        if self._password:
            password = self._password
            self._password = None
            await self.command("AUTH", password)
        if self._name:
            await self.command("CLIENT", "SETNAME", self._name)
        return self

    def _send_command(self, *args: bytes) -> None:
        assert self._writer
        self._last_sent = args
        self._writer.write(construct_command(*args))

    async def _read(self) -> Union[str, int, List[Union[str, int]]]:
        assert self._reader
        while (response := self._parser.gets()) is False:
            data = await self._reader.readuntil(b"\r\n")
            self._parser.feed(data)
        if isinstance(response, RedisError):
            raise response
        # logger.debug("< %s (%s)", response, type(response))
        return response

    async def _buffer_execute(
        self,
        command_buffer: bytes,
        transaction: bool = False,
        ignore_results: bool = False,
    ) -> Any:
        assert self._writer and self._reader
        if self._multi:
            raise ClientError("Cannot execute buffer during transaction.")
        if not command_buffer:
            raise ClientError("Attempted to execute empty buffer.")
        token = secrets.token_hex(8).encode()

        if transaction:
            self._send_command(b"MULTI")
        self._writer.write(command_buffer)
        if transaction:
            self._send_command(b"EXEC")
        self._send_command(b"ECHO", token)

        if ignore_results:
            # for the speed freaks:
            # we don't care about any of the responses, just read from
            # the server until we hit our token and discard it.
            await self._reader.readuntil(b"%s\r\n" % token)
            return None

        parser = self._parser

        parser.feed(await self._reader.readuntil(b"%s\r\n" % token))
        results = []

        check_token = token.decode() if self._encoding else token

        while (response := parser.gets()) != check_token:
            if not transaction or isinstance(response, list):
                results.append(response)
        if transaction:
            assert len(results) == 1
        return results[0] if transaction else results

    async def close(self) -> None:
        assert self._writer
        self._writer.close()
        await self._writer.wait_closed()

    @asynccontextmanager
    async def transaction(
        self,
    ) -> AsyncGenerator["RedisClient", None]:
        await self.multi()
        try:
            yield self
        finally:
            if self._multi:
                await self.discard()

    @property
    def in_multi(self) -> bool:
        return self._multi

    @property
    def is_closed(self) -> bool:
        assert self._reader and self._writer
        return self._reader.at_eof() or self._writer.is_closing()

    @property
    def database(self) -> int:
        return self._db

    def pipeline(self) -> Pipeline:
        return Pipeline(self)

    async def set(
        self,
        key: str,
        val: str,
        expire: Optional[int] = None,
    ) -> None:
        if expire:
            self._send_command(
                b"SET",
                key.encode(),
                val.encode(),
                b"EX",
                str(expire).encode(),
            )
        else:
            self._send_command(b"SET", key.encode(), val.encode())
        response = await self._read()
        if self._multi:
            assert response == "QUEUED"
        else:
            assert response == "OK"

    async def select(self, database: int) -> None:
        self._send_command(b"SELECT", str(database).encode())
        assert await self._read() == "OK"
        self._db = database

    async def command(self, *args: str) -> Any:
        self._send_command(*[a.encode() for a in args])
        return await self._read()

    async def bytes_command(self, *args: bytes) -> Any:
        self._send_command(*args)
        return await self._read()

    async def get(self, key: str) -> str:
        return await self.command("GET", key)

    async def multi(self) -> None:
        assert not self._multi
        self._send_command(b"MULTI")
        self._multi = True
        assert await self._read() == "OK"

    async def execute(self) -> Any:
        assert self._multi
        self._send_command(b"EXEC")
        self._multi = False
        return await self._read()

    async def discard(self) -> None:
        assert self._multi
        self._send_command(b"DISCARD")
        self._multi = False
        response = await self._read()
        assert response == "OK"

    async def swap(self, database: int, follow: bool = False) -> bool:
        self._send_command(
            b"SWAPDB",
            str(self._db).encode(),
            str(database).encode(),
        )
        response = await self._read()
        assert response == "OK"
        if follow:
            await self.select(database)
        return True

    # generic

    async def type(self, key: str) -> str:
        return await self.command("TYPE", key)

    async def ttl(self, key: str) -> int:
        return await self.command("TTL", key)

    # connection

    async def ping(self, latency: bool = False) -> Union[str, int]:
        if latency:
            start = time.perf_counter()
            assert await self.bytes_command(b"PING") == "PONG"
            return int((time.perf_counter() - start) * 1000)
        return await self.bytes_command(b"PING")

    # strings

    async def getset(self, key: str, val: str) -> str:
        return await self.command("GETSET", key, val)

    # sets

    async def sadd(self, key: str, *members: str) -> int:
        return await self.command("SADD", key, *members)

    async def smembers(self, key: str) -> Set[Any]:
        return set(await self.command("SMEMBERS", key))

    # hashes

    async def hset(
        self,
        key: str,
        set_dict: Dict[Any, Any],
        overwrite: bool = False,
    ) -> int:
        if not set_dict:
            raise ClientError("Cannot set empty dict")
        if overwrite:
            await self.command("DEL", key)
        return await self.command(
            "HSET",
            key,
            *itertools.chain.from_iterable(set_dict.items()),
        )

    async def hget(self, key: str, field: str) -> str:
        return await self.command("HGET", key, field)

    async def hmget(self, key: str, *fields: str) -> List[Optional[str]]:
        return await self.command("HMGET", key, *fields)

    async def hvals(self, key: str) -> List[str]:
        return await self.command("HVALS", key)

    async def hkeys(self, key: str) -> List[str]:
        return await self.command("HKEYS", key)

    async def hlen(self, key: str) -> int:
        return await self.command("HLEN", key)

    async def hgetall(self, key: str) -> Dict[Any, Any]:
        r = await self.command("HGETALL", key)
        return dict(itertools.zip_longest(*[iter(r)] * 2, fillvalue=""))
