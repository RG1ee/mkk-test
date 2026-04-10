from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    db: str = "payments"

    @property
    def url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class RabbitmqSettings(BaseModel):
    host: str = "localhost"
    port: int = 5672
    user: str = "guest"
    password: str = "guest"

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"


class PaymentSettings(BaseModel):
    max_attempts: int = 3
    gateway_min_delay: float = 2.0
    gateway_max_delay: float = 5.0
    gateway_success_rate: float = 0.9


class WebhookSettings(BaseModel):
    max_retries: int = 3
    timeout: float = 5.0


class OutboxSettings(BaseModel):
    poll_interval: float = 1.0
    batch_size: int = 100


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_nested_delimiter="__",
        env_file=".env",
    )

    api_key: str = "secret"

    postgres: PostgresSettings = PostgresSettings()
    rabbitmq: RabbitmqSettings = RabbitmqSettings()
    payment: PaymentSettings = PaymentSettings()
    webhook: WebhookSettings = WebhookSettings()
    outbox: OutboxSettings = OutboxSettings()


settings = Settings()
