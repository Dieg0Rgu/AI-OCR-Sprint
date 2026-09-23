import json
import re
import time
from typing import AsyncGenerator, Dict, List, Optional
from app.core.logging import logger
from app.schemas.chat import Citation, RAGResponse, ChatMessage
from app.schemas.documents import DocumentChunk
from app.services.providers.factory import ProviderFactory
from app.services.retrieval.cache import retrieval_cache
from app.services.retrieval.hybrid_search import hybrid_retriever


class RAGEngine:
    """
    RAG Engine with Hybrid Retrieval (Qdrant + BM25 via RRF) and
    Verifiable Source Citations.
    """

    SYSTEM_PROMPT = (
        "Eres un analista experto de documentos técnicos y científicos de alta fidelidad. "
        "Tu objetivo es responder con precisión a la pregunta del usuario basándote EXCLUSIVAMENTE "
        "en los fragmentos de contexto proporcionados a continuación.\n\n"
        "REGLAS ESTRICTAS:\n"
        "1. No asumas ni inventes hechos ajenos al contexto proporcionado (cero alucinación).\n"
        "2. Si la información necesaria para responder no está en el contexto, di claramente: "
        "'El documento analizado no contiene información suficiente para responder a esta pregunta.'\n"
        "3. Siempre que hagas una afirmación basada en un fragmento, referencia la fuente con la etiqueta: "
        "[CHUNK_ID: <id> | PAGINA: <numero>].\n"
        "4. Responde en el mismo idioma en que fue formulada la pregunta (por defecto en español)."
    )

    async def answer_query(
        self,
        document_id: str,
        query: str,
        top_k: int = 5,
        conversation_history: Optional[List[ChatMessage]] = None,
    ) -> RAGResponse:
        total_start = time.perf_counter()

        # 1. Hybrid Retrieval with caching
        cached_candidates = retrieval_cache.get(document_id, query, top_k)
        if cached_candidates is not None:
            fused_candidates, retrieval_time = cached_candidates, 0.0001
        else:
            fused_candidates, retrieval_time = await hybrid_retriever.search(
                query=query,
                document_id=document_id,
                top_k=top_k,
            )
            if fused_candidates:
                retrieval_cache.set(document_id, query, top_k, fused_candidates)

        if not fused_candidates:
            total_time = time.perf_counter() - total_start
            return RAGResponse(
                answer="No se encontraron secciones relevantes en el documento para responder a esta consulta.",
                citations=[],
                metrics={
                    "retrieval_time": round(retrieval_time, 4),
                    "llm_time": 0.0,
                    "total_time": round(total_time, 4),
                },
            )

        # 2. Build Context Prompt
        context_blocks = []
        chunk_map: Dict[str, DocumentChunk] = {}

        for item in fused_candidates:
            chunk = item.chunk
            chunk_map[chunk.chunk_id] = chunk
            block_header = f"[CHUNK_ID: {chunk.chunk_id} | PAGINA: {chunk.page_number}]"
            context_blocks.append(f"{block_header}\n{chunk.text.strip()}")

        context_str = "\n\n---\n\n".join(context_blocks)

        prompt = (
            f"CONTEXTO RECUPERADO DEL DOCUMENTO:\n"
            f"{context_str}\n\n"
            f"---\n"
            f"Pregunta del usuario: {query}\n"
            f"Respuesta fundamentada:"
        )

        # 3. LLM Generation
        llm_start = time.perf_counter()
        llm_provider = ProviderFactory.get_llm_provider()

        try:
            raw_answer = await llm_provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=512,
                temperature=0.1,
            )
        except Exception as e:
            logger.warning(
                "LLM provider failed, falling back to local extractor",
                extra={"error": str(e)},
            )
            from app.services.providers.local_provider import FallbackLLMProvider

            raw_answer = await FallbackLLMProvider().generate(prompt=prompt)

        llm_time = time.perf_counter() - llm_start

        # 4. Extract and Validate Citations
        citations = self._extract_citations(raw_answer, fused_candidates, chunk_map)

        total_time = time.perf_counter() - total_start
        metrics = {
            "retrieval_time": round(retrieval_time, 4),
            "llm_time": round(llm_time, 4),
            "total_time": round(total_time, 4),
        }

        logger.info(
            "RAG response generated",
            extra={
                "document_id": document_id,
                "citations_count": len(citations),
                "metrics": metrics,
            },
        )

        return RAGResponse(
            answer=raw_answer,
            citations=citations,
            metrics=metrics,
        )

    async def answer_query_stream(
        self,
        document_id: str,
        query: str,
        top_k: int = 5,
        conversation_history: Optional[List[ChatMessage]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Server-Sent Events (SSE) streaming generator.
        Emits:
          1. 'event: citations' with immediate source chunk references.
          2. 'event: token' as each incremental token is generated.
          3. 'event: metrics' with TTFT, throughput (tokens/sec), and latencies.
          4. 'event: done' marker.
        """
        total_start = time.perf_counter()

        # 1. Hybrid Retrieval with caching
        cached_candidates = retrieval_cache.get(document_id, query, top_k)
        if cached_candidates is not None:
            fused_candidates, retrieval_time = cached_candidates, 0.0001
        else:
            fused_candidates, retrieval_time = await hybrid_retriever.search(
                query=query,
                document_id=document_id,
                top_k=top_k,
            )
            if fused_candidates:
                retrieval_cache.set(document_id, query, top_k, fused_candidates)

        if not fused_candidates:
            err_data = {
                "answer": "No se encontraron secciones relevantes en el documento para responder a esta consulta.",
                "citations": [],
                "metrics": {
                    "retrieval_time": round(retrieval_time, 4),
                    "total_time": round(time.perf_counter() - total_start, 4),
                    "ttft": 0.0,
                    "tokens_per_sec": 0.0,
                },
            }
            yield f"event: error\ndata: {json.dumps(err_data)}\n\n"
            yield "event: done\ndata: [DONE]\n\n"
            return

        # 2. Build Context Prompt
        context_blocks = []
        chunk_map: Dict[str, DocumentChunk] = {}

        for item in fused_candidates:
            chunk = item.chunk
            chunk_map[chunk.chunk_id] = chunk
            block_header = f"[CHUNK_ID: {chunk.chunk_id} | PAGINA: {chunk.page_number}]"
            context_blocks.append(f"{block_header}\n{chunk.text.strip()}")

        context_str = "\n\n---\n\n".join(context_blocks)
        prompt = (
            f"CONTEXTO RECUPERADO DEL DOCUMENTO:\n"
            f"{context_str}\n\n"
            f"---\n"
            f"Pregunta del usuario: {query}\n"
            f"Respuesta fundamentada:"
        )

        # 3. Emit immediate verifiable citations
        immediate_citations = []
        for item in fused_candidates[:3]:
            c = item.chunk
            immediate_citations.append({
                "page_number": c.page_number,
                "chunk_id": c.chunk_id,
                "snippet": self._make_snippet(c.text),
            })
        yield f"event: citations\ndata: {json.dumps(immediate_citations)}\n\n"

        # 4. Stream tokens
        llm_provider = ProviderFactory.get_llm_provider()
        llm_start = time.perf_counter()
        first_token_time: Optional[float] = None
        token_count = 0
        collected_tokens: List[str] = []

        try:
            async for token in llm_provider.generate_stream(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=512,
                temperature=0.1,
            ):
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                    ttft = round(first_token_time - total_start, 4)
                    yield f"event: ttft\ndata: {json.dumps({'ttft': ttft})}\n\n"

                token_count += 1
                collected_tokens.append(token)
                yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.warning(
                "Streaming from primary LLM provider failed, falling back to local extractor",
                extra={"error": str(e)},
            )
            from app.services.providers.local_provider import FallbackLLMProvider
            async for token in FallbackLLMProvider().generate_stream(prompt=prompt, max_tokens=512):
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                    ttft = round(first_token_time - total_start, 4)
                    yield f"event: ttft\ndata: {json.dumps({'ttft': ttft})}\n\n"
                token_count += 1
                collected_tokens.append(token)
                yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

        # 5. Extract citations from accumulated text (or fallback to top chunks)
        full_answer = "".join(collected_tokens)
        validated_citations = self._extract_citations(full_answer, fused_candidates, chunk_map)
        if validated_citations:
            yield f"event: citations\ndata: {json.dumps([c.model_dump() for c in validated_citations])}\n\n"

        now = time.perf_counter()
        total_duration = now - total_start
        ttft = (first_token_time - total_start) if first_token_time else total_duration
        generation_duration = max((now - (first_token_time or llm_start)), 0.001)
        tokens_per_sec = round(token_count / generation_duration, 1)

        metrics = {
            "retrieval_time": round(retrieval_time, 4),
            "ttft": round(ttft, 4),
            "total_time": round(total_duration, 4),
            "token_count": token_count,
            "tokens_per_sec": tokens_per_sec,
        }

        yield f"event: metrics\ndata: {json.dumps(metrics)}\n\n"
        yield "event: done\ndata: [DONE]\n\n"

    def _extract_citations(
        self,
        answer: str,
        fused_candidates: List,
        chunk_map: Dict[str, DocumentChunk],
    ) -> List[Citation]:
        citations: List[Citation] = []
        seen_chunk_ids = set()

        # Regex pattern matching: [CHUNK_ID: ... | PAGINA: ...]
        pattern = r"\[CHUNK_ID:\s*([^\s\|\]]+)(?:\s*\|\s*PAGINA:\s*(\d+))?\]"
        matches = re.findall(pattern, answer)

        for match in matches:
            cid = match[0].strip()
            if cid in chunk_map and cid not in seen_chunk_ids:
                seen_chunk_ids.add(cid)
                chunk = chunk_map[cid]
                # Extract first meaningful sentence as snippet
                snippet = self._make_snippet(chunk.text)
                citations.append(
                    Citation(
                        page_number=chunk.page_number,
                        chunk_id=chunk.chunk_id,
                        snippet=snippet,
                    )
                )

        # Fallback: If model did not emit bracketed citations, cite the top fused chunks used
        if not citations and fused_candidates:
            for item in fused_candidates[:2]:
                chunk = item.chunk
                if chunk.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk.chunk_id)
                    citations.append(
                        Citation(
                            page_number=chunk.page_number,
                            chunk_id=chunk.chunk_id,
                            snippet=self._make_snippet(chunk.text),
                        )
                    )

        return citations

    def _make_snippet(self, text: str, max_chars: int = 160) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= max_chars:
            return cleaned
        # Cut at word boundary
        cutoff = cleaned[:max_chars].rfind(" ")
        return cleaned[: cutoff if cutoff > 50 else max_chars] + "..."


rag_engine = RAGEngine()
