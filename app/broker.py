from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitQueue

dlx_exchange = RabbitExchange("payments.dlx", durable=True)

payments_queue = RabbitQueue(
    "payments.new",
    durable=True,
    arguments={
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": "payments.new.dlq",
    },
)

dlq_queue = RabbitQueue("payments.new.dlq", durable=True)


async def declare_topology(broker: RabbitBroker) -> None:
    await broker.declare_exchange(dlx_exchange)
    await broker.declare_queue(payments_queue)
    await broker.declare_queue(dlq_queue)
