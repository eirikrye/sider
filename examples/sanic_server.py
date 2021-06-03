import sanic
import sanic.exceptions
import sanic.response
from sanic.response import HTTPResponse
from sanic.request import Request
from sider import RedisPool

app = sanic.Sanic("redis")
pool = RedisPool(host="localhost", size=2)

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)-15s] [%(name)s] [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


@app.exception(sanic.exceptions.NotFound)
def handle_404(request: Request, exception):
    return sanic.response.text("404", 404)


@app.listener("after_server_stop")
async def drain_pool(app: sanic.Sanic, loop):
    await pool.drain()


@app.middleware("request")
async def request_middleware(request: Request) -> None:
    request.ctx.client = await pool.get()


@app.middleware("response")
async def response_middleware(request: Request, response: HTTPResponse) -> None:
    if hasattr(request.ctx, "client"):
        await pool.put(request.ctx.client)


@app.route("/")
async def hello_world(request: Request) -> HTTPResponse:
    client = request.ctx.client
    async with client.transaction() as p:
        await client.get("hello")
        resp = await p.execute()
    return sanic.response.text(resp[0])


if __name__ == "__main__":
    app.run()
