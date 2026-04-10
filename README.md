# Payment Processing Service

Асинхронный микросервис для обработки платежей. Принимает запросы на оплату через REST API, публикует события в RabbitMQ через Outbox pattern, consumer эмулирует обработку платежа (2-5 сек, 90% успех), обновляет статус в БД и отправляет webhook клиенту.

## Стек

- **Python 3.13** + **uv** (пакетный менеджер)
- **FastAPI** + **Pydantic v2** (API)
- **SQLAlchemy 2.0** (async) + **PostgreSQL 16** + **Alembic** (БД и миграции)
- **FastStream** + **RabbitMQ 3** (брокер сообщений)
- **httpx** (webhook клиент)
- **Docker Compose** (инфраструктура)

## Архитектура

Три отдельных процесса вокруг общей БД и RabbitMQ:

```
┌─────────────┐      ┌───────────────┐       ┌──────────────┐
│   Client    │─────▶│      API      │──────▶│  PostgreSQL  │
└─────────────┘      │   (FastAPI)   │       │              │
                     └───────────────┘       │  payments    │
                                             │  outbox      │
                     ┌───────────────┐       │              │
                     │ Outbox Relay  │──────▶│              │
                     │   (worker)    │       └──────────────┘
                     └───────┬───────┘              ▲
                             │                      │
                             ▼                      │
                     ┌───────────────┐              │
                     │   RabbitMQ    │              │
                     │  payments.new │              │
                     └───────┬───────┘              │
                             │                      │
                             ▼                      │
                     ┌───────────────┐              │
                     │   Consumer    │──────────────┘
                     │   (worker)    │
                     └───────┬───────┘
                             │
                             ▼ webhook
                     ┌───────────────┐
                     │ Client (URL)  │
                     └───────────────┘
```

### Outbox Pattern

При создании платежа в одной транзакции записываются и запись в `payments`, и событие в `outbox_events`. Отдельный процесс `outbox-relay` раз в секунду опрашивает таблицу и публикует накопленные события в RabbitMQ. Это гарантирует, что событие не потеряется, даже если RabbitMQ временно недоступен в момент создания платежа.

### Dead Letter Queue

Очередь `payments.new` сконфигурирована с `x-dead-letter-exchange: payments.dlx`. Consumer делает до 3 попыток обработать сообщение с экспоненциальной задержкой (1с, 2с, 4с). Если все попытки провалились — сообщение отклоняется и попадает в `payments.new.dlq`.

### Идемпотентность

Заголовок `Idempotency-Key` сохраняется в БД с unique-индексом. Повторный запрос с тем же ключом возвращает ранее созданный платёж, не создавая дубль.

## Структура проекта

```
app/
  main.py                     # FastAPI entry point
  config.py                   # Настройки (pydantic-settings, nested)
  db.py                       # Async engine + session factory
  uow.py                      # UnitOfWork (+ abstract)
  models.py                   # SQLAlchemy ORM
  schemas.py                  # Pydantic схемы

  api/
    router.py                 # POST/GET /api/v1/payments
    dependencies.py           # Auth, DI

  repositories/
    base.py                   # AbstractRepository + SQLAlchemyRepository
    payment.py                # PaymentRepository
    outbox.py                 # OutboxRepository

  services/
    payment.py                # PaymentService (create/get)
    payment_processor.py      # PaymentProcessor (обработка + retry)
    outbox_relay.py           # OutboxRelay (polling loop)
    webhook.py                # send_webhook

  broker/
    topology.py               # Очереди, обменники, DLQ

  workers/
    consumer.py               # Entry point: FastStream consumer
    outbox_relay.py           # Entry point: outbox worker

alembic/
  env.py
  versions/                   # Миграции

Dockerfile
docker-compose.yml
pyproject.toml
.env.example
```

## Запуск через Docker Compose

### 1. Подготовка

```bash
cp .env.example .env
```

При необходимости отредактируйте значения в `.env` (пароли, ключи, параметры обработки).

### 2. Запуск всего стека

```bash
docker compose up --build -d
```

Compose поднимет:
- `postgres` — БД
- `rabbitmq` — брокер (UI на [http://localhost:15672](http://localhost:15672), логин/пароль из `.env`)
- `migrate` — одноразовый job, применяет миграции через `alembic upgrade head`
- `api` — FastAPI на [http://localhost:8000](http://localhost:8000)
- `outbox-relay` — воркер публикации outbox событий
- `consumer` — обработчик платежей

Порядок запуска управляется через `depends_on` с `service_completed_successfully` для миграций.

### 3. Проверка

```bash
docker compose ps
docker compose logs -f consumer
```

### 4. Остановка

```bash
docker compose down          # остановить контейнеры
docker compose down -v       # + удалить volume с данными
```

## Локальная разработка

Требуется установленный `uv`.

```bash
# Установить зависимости
uv sync

# Поднять только БД и брокер
docker compose up -d postgres rabbitmq

# Применить миграции
uv run alembic upgrade head

# Запустить API (в отдельных терминалах)
uv run uvicorn app.main:app --reload --port 8000
uv run python -m app.workers.outbox_relay
uv run python -m app.workers.consumer
```

## API

Все эндпоинты требуют заголовок `X-API-Key` (значение из `APP_API_KEY`).

### POST /api/v1/payments

Создать платёж. Обязательный заголовок `Idempotency-Key`.

**Запрос:**
```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: secret" \
  -H "Idempotency-Key: order-12345" \
  -d '{
    "amount": 1000.50,
    "currency": "RUB",
    "description": "Оплата заказа #12345",
    "metadata": {"order_id": 12345, "user_id": 42},
    "webhook_url": "https://my-shop.com/payment-callback"
  }'
```

**Ответ (202 Accepted):**
```json
{
  "id": "4f851d53-c7f3-44e4-8a90-884a9c752e1a",
  "status": "pending",
  "created_at": "2026-04-10T10:43:17.943191Z"
}
```

Поля тела запроса:
- `amount` — сумма (decimal, > 0)
- `currency` — `RUB` / `USD` / `EUR`
- `description` — строка (опционально)
- `metadata` — произвольный JSON-объект (опционально)
- `webhook_url` — URL для уведомления о результате (опционально)

### GET /api/v1/payments/{payment_id}

Получить детали платежа.

**Запрос:**
```bash
curl http://localhost:8000/api/v1/payments/4f851d53-c7f3-44e4-8a90-884a9c752e1a \
  -H "X-API-Key: secret"
```

**Ответ (200 OK):**
```json
{
  "id": "4f851d53-c7f3-44e4-8a90-884a9c752e1a",
  "amount": "1000.50",
  "currency": "RUB",
  "description": "Оплата заказа #12345",
  "metadata": {"order_id": 12345, "user_id": 42},
  "status": "succeeded",
  "idempotency_key": "order-12345",
  "webhook_url": "https://my-shop.com/payment-callback",
  "created_at": "2026-04-10T10:43:17.943191Z",
  "processed_at": "2026-04-10T10:43:22.032976Z"
}
```

Статусы: `pending` → `succeeded` | `failed`

### Webhook

После обработки платежа сервис делает POST на `webhook_url` с телом:
```json
{
  "payment_id": "4f851d53-c7f3-44e4-8a90-884a9c752e1a",
  "status": "succeeded"
}
```

При ошибках доставки — 3 попытки с экспоненциальной задержкой (1с, 2с, 4с).

## Переменные окружения

Все переменные с префиксом `APP_`. Вложенные группы разделяются `__`.

### PostgreSQL
| Переменная | По умолчанию | Описание |
|---|---|---|
| `APP_POSTGRES__HOST` | `localhost` | Хост БД |
| `APP_POSTGRES__PORT` | `5432` | Порт |
| `APP_POSTGRES__USER` | `postgres` | Пользователь |
| `APP_POSTGRES__PASSWORD` | `postgres` | Пароль |
| `APP_POSTGRES__DB` | `payments` | Имя БД |

### RabbitMQ
| Переменная | По умолчанию | Описание |
|---|---|---|
| `APP_RABBITMQ__HOST` | `localhost` | Хост брокера |
| `APP_RABBITMQ__PORT` | `5672` | Порт AMQP |
| `APP_RABBITMQ__USER` | `guest` | Пользователь |
| `APP_RABBITMQ__PASSWORD` | `guest` | Пароль |

### API
| Переменная | По умолчанию | Описание |
|---|---|---|
| `APP_API_KEY` | `secret` | Статический API ключ (`X-API-Key`) |

### Обработка платежей
| Переменная | По умолчанию | Описание |
|---|---|---|
| `APP_PAYMENT__MAX_ATTEMPTS` | `3` | Попыток обработки перед DLQ |
| `APP_PAYMENT__GATEWAY_MIN_DELAY` | `2.0` | Мин. задержка эмуляции (сек) |
| `APP_PAYMENT__GATEWAY_MAX_DELAY` | `5.0` | Макс. задержка эмуляции (сек) |
| `APP_PAYMENT__GATEWAY_SUCCESS_RATE` | `0.9` | Вероятность успеха (0..1) |

### Webhook
| Переменная | По умолчанию | Описание |
|---|---|---|
| `APP_WEBHOOK__MAX_RETRIES` | `3` | Попыток доставки |
| `APP_WEBHOOK__TIMEOUT` | `5.0` | Timeout запроса (сек) |

### Outbox Relay
| Переменная | По умолчанию | Описание |
|---|---|---|
| `APP_OUTBOX__POLL_INTERVAL` | `1.0` | Интервал опроса (сек) |
| `APP_OUTBOX__BATCH_SIZE` | `100` | Событий за один проход |

## Миграции

```bash
# Создать новую миграцию
uv run alembic revision --autogenerate -m "description"

# Применить
uv run alembic upgrade head

# Откатить на одну версию
uv run alembic downgrade -1
```

## Проверка работоспособности

После `docker compose up -d`:

1. **Создание платежа возвращает 202:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/payments \
     -H "X-API-Key: secret" \
     -H "Idempotency-Key: test-1" \
     -H "Content-Type: application/json" \
     -d '{"amount": 100, "currency": "RUB"}'
   ```

2. **Повторный запрос с тем же `Idempotency-Key` возвращает тот же `payment_id`.**

3. **Через 2-5 секунд статус меняется** с `pending` на `succeeded` или `failed`:
   ```bash
   curl http://localhost:8000/api/v1/payments/<id> -H "X-API-Key: secret"
   ```

4. **Без `X-API-Key` сервис возвращает 422.**

5. **DLQ:** при искусственной ошибке в consumer сообщение через 3 попытки попадает в `payments.new.dlq` (видно в RabbitMQ UI).
