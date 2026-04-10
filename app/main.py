from faststream.rabbit.fastapi import RabbitRouter
from fastapi import FastAPI

from app.api.router import router
from app.broker.topology import declare_topology
from app.config import settings

rabbit_router = RabbitRouter(settings.rabbitmq.url)


@rabbit_router.after_startup
async def on_startup(_app: object) -> None:
    assert rabbit_router.broker
    await declare_topology(rabbit_router.broker)


app = FastAPI(title="Payment Processing Service")
app.include_router(router)
app.include_router(rabbit_router)
