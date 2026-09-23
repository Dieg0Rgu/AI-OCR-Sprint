import httpx
from typing import Optional
from app.core.config import settings
from app.core.logging import logger
from app.services.providers.base import EmbeddingProvider, LLMProvider, VisionProvider
from app.services.providers.ollama_provider import (
    OllamaEmbeddingProvider,
    OllamaLLMProvider,
    OllamaVisionProvider,
)
from app.services.providers.local_provider import (
    FastEmbedEmbeddingProvider,
    FallbackLLMProvider,
    FallbackVisionProvider,
)


class ProviderFactory:
    _embedding_provider: Optional[EmbeddingProvider] = None
    _llm_provider: Optional[LLMProvider] = None
    _vision_provider: Optional[VisionProvider] = None

    @classmethod
    async def is_ollama_available(cls) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    @classmethod
    def get_embedding_provider(cls, force_local: bool = False) -> EmbeddingProvider:
        if cls._embedding_provider is not None and not force_local:
            return cls._embedding_provider

        if force_local or settings.FALLBACK_EMBEDDINGS:
            cls._embedding_provider = FastEmbedEmbeddingProvider()
        else:
            cls._embedding_provider = OllamaEmbeddingProvider()
        return cls._embedding_provider

    @classmethod
    def set_embedding_provider(cls, provider: EmbeddingProvider) -> None:
        cls._embedding_provider = provider

    @classmethod
    def get_llm_provider(cls) -> LLMProvider:
        if cls._llm_provider is not None:
            return cls._llm_provider
        cls._llm_provider = OllamaLLMProvider()
        return cls._llm_provider

    @classmethod
    def set_llm_provider(cls, provider: LLMProvider) -> None:
        cls._llm_provider = provider

    @classmethod
    def get_vision_provider(cls) -> VisionProvider:
        if cls._vision_provider is not None:
            return cls._vision_provider
        cls._vision_provider = OllamaVisionProvider()
        return cls._vision_provider

    @classmethod
    def set_vision_provider(cls, provider: VisionProvider) -> None:
        cls._vision_provider = provider
