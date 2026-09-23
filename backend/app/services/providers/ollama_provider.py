import base64
import json
from pathlib import Path
from typing import AsyncGenerator, List, Optional
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from app.core.config import settings
from app.core.logging import logger
from app.services.providers.base import EmbeddingProvider, LLMProvider, VisionProvider


class OllamaClientBase:
    """Base client with connection pooling and configurable retry logic."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=10.0),
        )

    async def aclose(self):
        await self.client.aclose()


class OllamaEmbeddingProvider(OllamaClientBase, EmbeddingProvider):
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        dimension: int = 768,
    ):
        super().__init__(base_url=base_url)
        self.model = model or settings.OLLAMA_EMBED_MODEL
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(settings.OLLAMA_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, 20),  # INFO level
        reraise=True,
    )
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            # Modern Ollama /api/embed supports batching
            response = await self.client.post(
                "/api/embed",
                json={"model": self.model, "input": texts},
            )
            if response.status_code == 200:
                data = response.json()
                embeddings = data.get("embeddings", [])
                if embeddings and len(embeddings) > 0:
                    self._dimension = len(embeddings[0])
                    return embeddings

            # Fallback to single-call /api/embeddings if /api/embed is unsupported
            embeddings = []
            for text in texts:
                res = await self.client.post(
                    "/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                res.raise_for_status()
                emb = res.json().get("embedding", [])
                if emb:
                    self._dimension = len(emb)
                embeddings.append(emb)
            return embeddings
        except Exception as e:
            logger.error("Ollama embedding failed", extra={"model": self.model, "error": str(e)})
            raise

    async def embed_query(self, query: str) -> List[float]:
        res = await self.embed_texts([query])
        return res[0] if res else [0.0] * self._dimension


class OllamaLLMProvider(OllamaClientBase, LLMProvider):
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        super().__init__(base_url=base_url)
        self.model = model or settings.OLLAMA_LLM_MODEL

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(settings.OLLAMA_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, 20),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        try:
            response = await self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error("Ollama chat generation failed", extra={"model": self.model, "error": str(e)})
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        try:
            async with self.client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk_data = json.loads(line)
                        token = chunk_data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if chunk_data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error("Ollama streaming chat failed", extra={"model": self.model, "error": str(e)})
            raise


class OllamaVisionProvider(OllamaClientBase, VisionProvider):
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        super().__init__(base_url=base_url)
        self.model = model or settings.OLLAMA_VISION_MODEL

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(settings.OLLAMA_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, 20),
        reraise=True,
    )
    async def analyze_image(
        self,
        image_path: Path,
        prompt: str,
        max_tokens: int = 1024,
    ) -> str:
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found at {image_path}")

        with open(image_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [encoded_image],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.2,
            },
        }

        try:
            response = await self.client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except Exception as e:
            logger.error("Ollama vision analysis failed", extra={"model": self.model, "image": str(image_path), "error": str(e)})
            raise
