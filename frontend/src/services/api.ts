import type {
  Citation,
  DocumentDetailResponse,
  DocumentUploadResponse,
  ExtractedImageMetadata,
  KeywordSearchResponse,
  RAGResponse,
  VisionQueryResponse,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export class ApiError extends Error {
  errorCode: string;
  statusCode: number;

  constructor(message: string, errorCode: string = 'ERROR_UNKNOWN', statusCode: number = 500) {
    super(message);
    this.name = 'ApiError';
    this.errorCode = errorCode;
    this.statusCode = statusCode;
  }
}

export class ApiService {
  /**
   * Pre-flight client-side inspection:
   * Validates file extension, max file size, and inspects the first 8 bytes for '%PDF-'.
   */
  static async validatePdfPreflight(file: File): Promise<{ valid: boolean; errorCode?: string; message?: string }> {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      return {
        valid: false,
        errorCode: 'ERROR_INVALID_EXTENSION',
        message: 'El archivo seleccionado no tiene extensión .pdf válida.',
      };
    }

    if (file.size === 0) {
      return {
        valid: false,
        errorCode: 'ERROR_EMPTY_PAYLOAD',
        message: 'El archivo seleccionado está vacío (0 bytes).',
      };
    }

    const MAX_MB = 50;
    if (file.size > MAX_MB * 1024 * 1024) {
      return {
        valid: false,
        errorCode: 'ERROR_SIZE_LIMIT_EXCEEDED',
        message: `El archivo (${(file.size / (1024 * 1024)).toFixed(2)} MB) supera el límite máximo de ${MAX_MB} MB.`,
      };
    }

    try {
      const headerSlice = file.slice(0, 8);
      const buffer = await headerSlice.arrayBuffer();
      const headerStr = new TextDecoder('ascii').decode(buffer);
      if (!headerStr.startsWith('%PDF-')) {
        return {
          valid: false,
          errorCode: 'ERROR_INVALID_MIME_OR_MAGIC',
          message: 'El archivo no contiene la cabecera mágica de un PDF legítimo (%PDF-).',
        };
      }
    } catch {
      // In case arrayBuffer read fails, let server perform final check
    }

    return { valid: true };
  }

  static async uploadDocument(file: File): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${BASE_URL}/documents/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const headerCode = res.headers.get('X-Error-Code');
      const err = await res.json().catch(() => ({ detail: 'Upload error' }));
      const errorCode = err.error_code || headerCode || `ERROR_HTTP_${res.status}`;
      throw new ApiError(err.detail || 'Fallo en la transferencia del archivo', errorCode, res.status);
    }

    return res.json();
  }

  static async listDocuments(): Promise<DocumentDetailResponse[]> {
    const res = await fetch(`${BASE_URL}/documents`);
    if (!res.ok) throw new ApiError('Error al obtener lista de documentos', 'ERROR_FETCH_DOCS', res.status);
    return res.json();
  }

  static async getDocument(documentId: string): Promise<DocumentDetailResponse> {
    const res = await fetch(`${BASE_URL}/documents/${documentId}`);
    if (!res.ok) throw new ApiError(`Documento '${documentId}' no encontrado`, 'ERROR_NOT_FOUND', res.status);
    return res.json();
  }

  static getDocumentFileUrl(documentId: string): string {
    return `${BASE_URL}/documents/${documentId}/file`;
  }

  static async listDocumentImages(documentId: string): Promise<ExtractedImageMetadata[]> {
    const res = await fetch(`${BASE_URL}/documents/${documentId}/images`);
    if (!res.ok) throw new ApiError('Error al obtener figuras del documento', 'ERROR_IMAGES', res.status);
    return res.json();
  }

  static getImageUrl(documentId: string, imageId: string): string {
    return `${BASE_URL}/documents/${documentId}/images/${imageId}`;
  }

  static async searchDocumentKeywords(
    documentId: string,
    query: string,
    caseSensitive = false,
    exactMatch = false
  ): Promise<KeywordSearchResponse> {
    const params = new URLSearchParams({
      q: query,
      case_sensitive: String(caseSensitive),
      exact: String(exactMatch),
    });

    const res = await fetch(`${BASE_URL}/documents/${documentId}/search?${params.toString()}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Search error' }));
      throw new ApiError(err.detail || 'Error en búsqueda léxica', 'ERROR_KEYWORD_SEARCH', res.status);
    }

    return res.json();
  }

  static async queryChat(
    documentId: string,
    query: string,
    topK = 5
  ): Promise<RAGResponse> {
    const res = await fetch(`${BASE_URL}/chat/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_id: documentId,
        query,
        top_k: topK,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Chat query error' }));
      throw new ApiError(err.detail || 'Fallo en consulta RAG', 'ERROR_CHAT', res.status);
    }

    return res.json();
  }

  static streamChat(
    documentId: string,
    query: string,
    callbacks: {
      onToken: (token: string) => void;
      onCitations: (citations: Citation[]) => void;
      onTtft: (ttft: number) => void;
      onMetrics: (metrics: Record<string, number>) => void;
      onDone: () => void;
      onError: (err: ApiError) => void;
    },
    topK = 5
  ): () => void {
    const controller = new AbortController();

    (async () => {
      try {
        const response = await fetch(`${BASE_URL}/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
          },
          body: JSON.stringify({
            document_id: documentId,
            query,
            top_k: topK,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({ detail: 'Error en stream' }));
          throw new ApiError(errData.detail || 'Error en streaming de respuesta', 'ERROR_STREAM', response.status);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new ApiError('Stream de respuesta no disponible', 'ERROR_NO_READER', 500);

        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const block of lines) {
            if (!block.trim()) continue;

            const blockLines = block.split('\n');
            let eventType = 'message';
            let dataStr = '';

            for (const l of blockLines) {
              if (l.startsWith('event:')) {
                eventType = l.slice(6).trim();
              } else if (l.startsWith('data:')) {
                dataStr = l.slice(5).trim();
              }
            }

            if (dataStr === '[DONE]' || eventType === 'done') {
              callbacks.onDone();
              return;
            }

            try {
              const parsed = JSON.parse(dataStr);
              if (eventType === 'citations') {
                callbacks.onCitations(parsed);
              } else if (eventType === 'token') {
                callbacks.onToken(parsed.token || '');
              } else if (eventType === 'ttft') {
                callbacks.onTtft(parsed.ttft || 0);
              } else if (eventType === 'metrics') {
                callbacks.onMetrics(parsed);
              } else if (eventType === 'error') {
                callbacks.onError(new ApiError(parsed.answer || 'Error en respuesta', 'ERROR_RAG', 400));
              }
            } catch {
              // Ignore non-json chunk fragments
            }
          }
        }

        callbacks.onDone();
      } catch (err: any) {
        if (err.name === 'AbortError') return;
        callbacks.onError(err instanceof ApiError ? err : new ApiError(err.message, 'ERROR_STREAM_FAILURE', 500));
      }
    })();

    return () => controller.abort();
  }

  static async queryVision(
    documentId: string,
    imageId: string,
    prompt: string
  ): Promise<VisionQueryResponse> {
    const res = await fetch(`${BASE_URL}/vision/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_id: documentId,
        image_id: imageId,
        prompt,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Vision query error' }));
      throw new ApiError(err.detail || 'Fallo en consulta de visión', 'ERROR_VISION', res.status);
    }

    return res.json();
  }
}
