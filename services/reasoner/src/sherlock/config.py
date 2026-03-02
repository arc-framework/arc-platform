from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHERLOCK_",
        env_ignore_empty=False,
        extra="ignore",
    )

    # Service identity
    service_name: str = Field("arc-sherlock", alias="SHERLOCK_SERVICE_NAME")
    service_version: str = Field("0.1.0", alias="SHERLOCK_VERSION")

    # PostgreSQL (Oracle — long-term conversation history)
    postgres_url: str = Field(
        "postgresql+asyncpg://arc:arc@arc-sql-db:5432/arc",
        alias="SHERLOCK_POSTGRES_URL",
    )

    # NATS (Flash — real-time request-reply)
    nats_url: str = Field("nats://arc-messaging:4222", alias="SHERLOCK_NATS_URL")
    nats_enabled: bool = Field(True, alias="SHERLOCK_NATS_ENABLED")
    nats_subject: str = Field("sherlock.request", alias="SHERLOCK_NATS_SUBJECT")
    nats_queue_group: str = Field("sherlock_workers", alias="SHERLOCK_NATS_QUEUE_GROUP")

    # Pulsar (Dr. Strange — durable async, opt-in)
    pulsar_url: str = Field(
        "pulsar://arc-streaming:6650", alias="SHERLOCK_PULSAR_URL"
    )
    pulsar_enabled: bool = Field(False, alias="SHERLOCK_PULSAR_ENABLED")
    pulsar_request_topic: str = Field(
        "persistent://public/default/sherlock-requests",
        alias="SHERLOCK_PULSAR_REQUEST_TOPIC",
    )
    pulsar_result_topic: str = Field(
        "persistent://public/default/sherlock-results",
        alias="SHERLOCK_PULSAR_RESULT_TOPIC",
    )
    pulsar_subscription: str = Field(
        "sherlock-workers", alias="SHERLOCK_PULSAR_SUBSCRIPTION"
    )

    # LLM (LM Studio — OpenAI-compatible)
    llm_model: str = Field("mistralai/mistral-7b-instruct-v0.3", alias="SHERLOCK_LLM_MODEL")
    llm_base_url: str = Field(
        "http://localhost:1234/v1", alias="SHERLOCK_LLM_BASE_URL"
    )
    # None (default) → auto-detected from model name by llm_factory.
    # Set True/False explicitly to override for edge cases (e.g. ChatML-format Llama fine-tune).
    llm_supports_system_role: bool | None = Field(None, alias="SHERLOCK_LLM_SUPPORTS_SYSTEM_ROLE")
    # System prompt injected into every reasoning request.
    # Override via SHERLOCK_SYSTEM_PROMPT for persona swaps or A/B deployments.
    system_prompt: str = Field(
        "You are Sherlock, an analytical reasoning assistant. "
        "Use the following conversation context to inform your reply.",
        alias="SHERLOCK_SYSTEM_PROMPT",
    )

    # Embeddings (sentence-transformers)
    embedding_model: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2", alias="SHERLOCK_EMBEDDING_MODEL"
    )
    embedding_dim: int = Field(384, alias="SHERLOCK_EMBEDDING_DIM")
    context_top_k: int = Field(5, alias="SHERLOCK_CONTEXT_TOP_K")

    # OTEL — standard env var name (no SHERLOCK_ prefix for otel_endpoint)
    otel_endpoint: str = Field(
        "http://arc-friday-collector:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    otel_traces_enabled: bool = Field(True, alias="SHERLOCK_OTEL_TRACES_ENABLED")
    otel_metrics_enabled: bool = Field(True, alias="SHERLOCK_OTEL_METRICS_ENABLED")
    otel_logs_enabled: bool = Field(True, alias="SHERLOCK_OTEL_LOGS_ENABLED")

    # Security: opt-in content tracing (default off — no message content in spans)
    content_tracing: bool = Field(False, alias="SHERLOCK_CONTENT_TRACING")

    # Dev mode: mounts /fake/* endpoints for rapid local testing (default off)
    dev_mode: bool = Field(True, alias="SHERLOCK_DEV_MODE")
