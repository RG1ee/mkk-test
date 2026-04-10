from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitQueue

DLX_EXCHANGE_NAME = "payments.dlx"
PAYMENTS_QUEUE_NAME = "payments.new"
DLQ_QUEUE_NAME = "payments.new.dlq"

dlx_exchange = RabbitExchange(DLX_EXCHANGE_NAME, durable=True)

payments_queue = RabbitQueue(
    PAYMENTS_QUEUE_NAME,
    durable=True,
    arguments={
        "x-dead-letter-exchange": DLX_EXCHANGE_NAME,
        "x-dead-letter-routing-key": DLQ_QUEUE_NAME,
    },
)

dlq_queue = RabbitQueue(DLQ_QUEUE_NAME, durable=True)


async def declare_topology(broker: RabbitBroker) -> None:
    await broker.declare_exchange(dlx_exchange)
    await broker.declare_queue(payments_queue)
    await broker.declare_queue(dlq_queue)
