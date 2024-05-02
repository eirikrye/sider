import sanic
import sanic.exceptions
import sanic.response
from sanic.request import Request
from sanic.response import HTTPResponse

from sider import RedisPool

app = sanic.Sanic("sider-demo")


@app.listener("after_server_stop")
async def drain_pool(app: sanic.Sanic, loop):
    if hasattr(app.ctx, "pool"):
        await app.ctx.pool.drain()


@app.listener("before_server_start")
async def setup_pool(app: sanic.Sanic, loop):
    app.ctx.pool = RedisPool(host="localhost", size=2)


@app.middleware("request")
async def request_middleware(request: Request) -> None:
    if hasattr(app.ctx, "pool"):
        pool = app.ctx.pool
        request.ctx.client = await pool.get()


@app.middleware("response")
async def response_middleware(request: Request, response: HTTPResponse) -> None:
    pool = app.ctx.pool
    if hasattr(request.ctx, "client"):
        await pool.put(request.ctx.client)


@app.get("/<key:string>")
async def get_key(request: Request, key: str) -> HTTPResponse:
    client = request.ctx.client
    value = await client.get(key)
    if not value:
        return sanic.response.raw(None, status=404)
    return sanic.response.text(await client.get(key) or "N/A")


@app.route("/<key:string>", methods=["PUT", "POST", "PATCH"])
async def set_key(request: Request, key: str) -> HTTPResponse:
    client = request.ctx.client
    await client.set(key, request.body.decode())
    return sanic.response.raw(None, status=204)


@app.delete("/<key:string>")
async def del_key(request: Request, key: str) -> HTTPResponse:
    client = request.ctx.client
    result = await client.command("DEL", key)
    if not result:
        return sanic.response.raw(None, status=404)
    return sanic.response.raw(None, status=204)


if __name__ == "__main__":
    app.run()
