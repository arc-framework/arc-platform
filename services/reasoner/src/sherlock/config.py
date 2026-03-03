from pydantic import Field, SecretStr
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

    # LLM provider selection
    llm_provider: str = Field("openai-compatible", alias="SHERLOCK_LLM_PROVIDER")
    llm_api_key: str = Field("", alias="SHERLOCK_LLM_API_KEY")
    openai_base_url: str | None = Field(None, alias="SHERLOCK_OPENAI_BASE_URL")
    google_project_id: str | None = Field(None, alias="SHERLOCK_GOOGLE_PROJECT_ID")

    # NATS v1 chat channels
    nats_v1_chat_subject: str = Field("sherlock.v1.chat", alias="SHERLOCK_NATS_V1_CHAT_SUBJECT")
    nats_v1_result_subject: str = Field(
        "sherlock.v1.result", alias="SHERLOCK_NATS_V1_RESULT_SUBJECT"
    )
    nats_v1_enabled: bool = Field(True, alias="SHERLOCK_NATS_V1_ENABLED")

    # AsyncAPI UI
    async_docs_enabled: bool = Field(True, alias="SHERLOCK_ASYNC_DOCS_ENABLED")

    # RAG (Universal RAG engine — feature 013)
    rag_enabled: bool = Field(False, alias="SHERLOCK_RAG_ENABLED")

    # MinIO (Tardis — object storage)
    minio_endpoint: str = Field("arc-storage:9000", alias="SHERLOCK_MINIO_ENDPOINT")
    minio_access_key: SecretStr = Field(SecretStr("minioadmin"), alias="SHERLOCK_MINIO_ACCESS_KEY")
    minio_secret_key: SecretStr = Field(SecretStr("minioadmin"), alias="SHERLOCK_MINIO_SECRET_KEY")
    minio_bucket: str = Field("sherlock-files", alias="SHERLOCK_MINIO_BUCKET")
    minio_secure: bool = Field(False, alias="SHERLOCK_MINIO_SECURE")

    # RAG tunables
    max_file_bytes: int = Field(50 * 1024 * 1024, alias="SHERLOCK_MAX_FILE_BYTES")  # 50 MB
    hybrid_alpha: float = Field(0.7, alias="SHERLOCK_HYBRID_ALPHA")
    chunk_size_tokens: int = Field(512, alias="SHERLOCK_CHUNK_SIZE_TOKENS")
    chunk_overlap_tokens: int = Field(50, alias="SHERLOCK_CHUNK_OVERLAP_TOKENS")
    retrieval_candidate_k: int = Field(50, alias="SHERLOCK_RETRIEVAL_CANDIDATE_K")
    retrieval_top_k: int = Field(5, alias="SHERLOCK_RETRIEVAL_TOP_K")
    reranker_model: str = Field(
        "cross-encoder/ms-marco-MiniLM-L-6-v2", alias="SHERLOCK_RERANKER_MODEL"
    )
    sync_timeout_s: float = Field(30.0, alias="SHERLOCK_SYNC_TIMEOUT_S")
