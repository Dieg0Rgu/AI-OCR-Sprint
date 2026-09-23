import { ref } from 'vue';
import type { ChatMessage, Citation } from '../types';
import { ApiService, ApiError } from '../services/api';

export function useChat() {
  const messages = ref<ChatMessage[]>([]);
  const isGenerating = ref<boolean>(false);
  const error = ref<string | null>(null);
  let abortStream: (() => void) | null = null;

  async function sendMessage(
    documentId: string,
    query: string,
    useStreaming: boolean = true
  ) {
    if (!query.trim() || isGenerating.value) return;

    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      role: 'user',
      content: query.trim(),
      timestamp: new Date().toLocaleTimeString(),
    };

    messages.value.push(userMsg);
    isGenerating.value = true;
    error.value = null;

    if (!useStreaming) {
      try {
        const response = await ApiService.queryChat(documentId, query);
        const assistantMsg: ChatMessage = {
          id: `ast_${Date.now()}`,
          role: 'assistant',
          content: response.answer,
          citations: response.citations,
          metrics: response.metrics,
          timestamp: new Date().toLocaleTimeString(),
        };
        messages.value.push(assistantMsg);
      } catch (err: any) {
        error.value = err.message || 'Error al procesar la respuesta';
        messages.value.push({
          id: `err_${Date.now()}`,
          role: 'assistant',
          content: `⚠️ Error: ${error.value}`,
          timestamp: new Date().toLocaleTimeString(),
        });
      } finally {
        isGenerating.value = false;
      }
      return;
    }

    // Streaming mode
    const assistantMsgId = `ast_${Date.now()}`;
    const assistantMsg = ref<ChatMessage>({
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      citations: [],
      metrics: {},
      timestamp: new Date().toLocaleTimeString(),
    });

    messages.value.push(assistantMsg.value);

    abortStream = ApiService.streamChat(
      documentId,
      query,
      {
        onToken: (token: string) => {
          assistantMsg.value.content += token;
        },
        onCitations: (citations: Citation[]) => {
          assistantMsg.value.citations = citations;
        },
        onTtft: (ttft: number) => {
          assistantMsg.value.metrics = {
            ...(assistantMsg.value.metrics || {}),
            ttft,
          };
        },
        onMetrics: (metrics: Record<string, number>) => {
          assistantMsg.value.metrics = {
            ...(assistantMsg.value.metrics || {}),
            ...metrics,
          };
        },
        onDone: () => {
          isGenerating.value = false;
          abortStream = null;
        },
        onError: (err: ApiError) => {
          isGenerating.value = false;
          abortStream = null;
          error.value = err.message;
          if (!assistantMsg.value.content) {
            assistantMsg.value.content = `[ERROR: ${err.errorCode}] ${err.message}`;
          }
        },
      }
    );
  }

  function stopGenerating() {
    if (abortStream) {
      abortStream();
      abortStream = null;
    }
    isGenerating.value = false;
  }

  function clearChat() {
    stopGenerating();
    messages.value = [];
    error.value = null;
  }

  return {
    messages,
    isGenerating,
    error,
    sendMessage,
    stopGenerating,
    clearChat,
  };
}
