"""Long-term memory service using mem0, pgvector, and Hugging Face embeddings."""

from typing import Any, Literal, Optional, cast, override

import httpx
from mem0 import AsyncMemory
from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase
import mem0.utils.factory as mem0_factory
import numpy as np

from app.core.cache import (
    cache_key,
    cache_service,
)
from app.core.config import settings
from app.core.logging import logger


class HuggingFaceInferenceEmbedding(EmbeddingBase):
    """Hugging Face serverless feature extraction embedding client for mem0."""

    def __init__(self, config: Optional[Any] = None):
        """Initialize Hugging Face inference embedding client."""
        if isinstance(config, dict):
            cfg = BaseEmbedderConfig(**config)
        else:
            cfg = config or BaseEmbedderConfig()
        cfg.embedding_dims = getattr(cfg, "embedding_dims", None) or settings.LONG_TERM_MEMORY_EMBEDDER_DIMS
        super().__init__(cfg)
        self.api_key = getattr(self.config, "api_key", None) or settings.HUGGINGFACE_TOKEN
        self.model = getattr(self.config, "model", None) or settings.LONG_TERM_MEMORY_EMBEDDER_MODEL
        self.endpoint = f"https://router.huggingface.co/hf-inference/models/{self.model}"
        self.client = httpx.Client(timeout=30.0)

    @override
    def embed(
        self, text: Any, memory_action: Optional[Literal["add", "search", "update"]] = None
    ) -> Any:
        """Generate text embedding vector using Hugging Face router inference API."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = self.client.post(self.endpoint, headers=headers, json={"inputs": text})
        resp.raise_for_status()
        data: Any = resp.json()
        arr = np.array(data)
        if arr.ndim == 1:
            return arr.tolist()
        elif arr.ndim == 2:
            return arr[0].tolist()
        elif arr.ndim == 3:
            return arr.mean(axis=1)[0].tolist()
        return cast(list[float], data)


# Register custom HuggingFace embedder into mem0's EmbedderFactory
_orig_factory_create = mem0_factory.EmbedderFactory.create


def _patched_factory_create(provider_name: str, config: Any, vector_config: Optional[dict] = None) -> Any:
    if provider_name == "huggingface":
        return HuggingFaceInferenceEmbedding(config)
    return _orig_factory_create(provider_name, config, vector_config)


mem0_factory.EmbedderFactory.create = _patched_factory_create


class _NoOpTelemetryVectorStore:
    """No-op vector store to bypass mem0's internal telemetry collection creation."""

    def get(self, *args: Any, **kwargs: Any) -> None:
        return None

    def insert(self, *args: Any, **kwargs: Any) -> None:
        pass

    def search(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    def delete(self, *args: Any, **kwargs: Any) -> None:
        pass

    def update(self, *args: Any, **kwargs: Any) -> None:
        pass

    def reset(self, *args: Any, **kwargs: Any) -> None:
        pass


# Prevent mem0 from creating internal 'mem0migrations' telemetry table in database
_orig_vector_factory_create = mem0_factory.VectorStoreFactory.create


def _patched_vector_factory_create(provider_name: str, config: Any) -> Any:
    if getattr(config, "collection_name", None) == "mem0migrations":
        return _NoOpTelemetryVectorStore()
    return _orig_vector_factory_create(provider_name, config)


mem0_factory.VectorStoreFactory.create = _patched_vector_factory_create


class MemoryService:
    """Service for managing long-term memory using mem0 and pgvector."""

    def __init__(self):
        """Initialize the memory service."""
        self._memory: AsyncMemory | None = None

    async def _get_memory(self) -> AsyncMemory:
        if self._memory is None:
            self._memory = await AsyncMemory.from_config(
                config_dict={
                    "vector_store": {
                        "provider": "pgvector",
                        "config": {
                            "collection_name": settings.LONG_TERM_MEMORY_COLLECTION_NAME,
                            "dbname": settings.POSTGRES_DB,
                            "user": settings.POSTGRES_USER,
                            "password": settings.POSTGRES_PASSWORD,
                            "host": settings.POSTGRES_HOST,
                            "port": settings.POSTGRES_PORT,
                            "embedding_model_dims": settings.LONG_TERM_MEMORY_EMBEDDER_DIMS,
                        },
                    },
                    "llm": {
                        "provider": "openai",
                        "config": {
                            "model": settings.LONG_TERM_MEMORY_MODEL,
                            "openai_base_url": settings.OPENAI_BASE_URL,
                            "api_key": settings.OPENAI_API_KEY,
                        },
                    },
                    "embedder": {
                        "provider": settings.EMBEDDER_PROVIDER,
                        "config": {
                            "model": settings.LONG_TERM_MEMORY_EMBEDDER_MODEL,
                            "api_key": settings.HUGGINGFACE_TOKEN,
                            "embedding_dims": settings.LONG_TERM_MEMORY_EMBEDDER_DIMS,
                        },
                    },
                }
            )
        return self._memory

    async def initialize(self) -> None:
        """Pre-warm the mem0 AsyncMemory instance and its pgvector connection pool.

        Call once at startup so the first search() or add() doesn't pay the
        ~130ms from_config + pgvector.list_cols() cold-init cost.
        """
        await self._get_memory()
        logger.info("memory_service_initialized")

    async def search(self, user_id: str | None, query: str) -> str:
        """Search relevant memories for a user.

        Checks cache first; on miss, queries mem0 and caches the result.

        Returns formatted memory string, or empty string on failure or when
        no user_id is supplied (anonymous sessions skip long-term memory
        rather than pooling under a shared partition).
        """
        if user_id is None:
            return ""
        try:
            # Check cache first
            key = cache_key("memory", str(user_id), query)
            cached = await cache_service.get(key)
            if cached is not None:
                logger.debug("memory_search_cache_hit", user_id=user_id)
                return cached

            memory = await self._get_memory()
            results = await memory.search(user_id=str(user_id), query=query)
            result = "\n".join([f"* {r['memory']}" for r in results["results"]])

            # Cache successful results
            if result:
                await cache_service.set(key, result)

            return result
        except Exception as e:
            logger.error("failed_to_get_relevant_memory", error=str(e), user_id=user_id, query=query)
            return ""

    async def add(self, user_id: str | None, messages: list[dict], metadata: dict | None = None) -> None:
        """Add messages to long-term memory for a user.

        No-op when ``user_id`` is ``None`` (see ``search`` for rationale).
        """
        if user_id is None:
            return
        try:
            memory = await self._get_memory()
            await memory.add(messages, user_id=str(user_id), metadata=metadata)
            logger.info("long_term_memory_updated_successfully", user_id=user_id)
        except Exception as e:
            logger.exception("failed_to_update_long_term_memory", user_id=user_id, error=str(e))


memory_service = MemoryService()
