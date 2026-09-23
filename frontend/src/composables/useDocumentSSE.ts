import { ref, computed } from 'vue';
import type { DocumentStatus, SSEEventPayload } from '../types';

export function useDocumentSSE() {
  const currentStatus = ref<DocumentStatus | null>(null);
  const progressPercent = ref<number>(0);
  const statusMessage = ref<string>('');
  const errorMessage = ref<string | null>(null);
  const stageLatencies = ref<Record<string, number>>({});
  const isConnected = ref<boolean>(false);

  let eventSource: EventSource | null = null;

  const isProcessing = computed(() => {
    return (
      currentStatus.value !== null &&
      currentStatus.value !== 'ready' &&
      currentStatus.value !== 'failed'
    );
  });

  const isReady = computed(() => currentStatus.value === 'ready');
  const isFailed = computed(() => currentStatus.value === 'failed');

  function startListening(
    documentId: string,
    callbacks?: {
      onReady?: (event: SSEEventPayload) => void;
      onError?: (error: string) => void;
    }
  ) {
    stopListening();

    const url = `/api/v1/documents/${documentId}/events`;
    eventSource = new EventSource(url);
    isConnected.value = true;

    eventSource.onmessage = (event) => {
      try {
        const payload: SSEEventPayload = JSON.parse(event.data);
        currentStatus.value = payload.status;
        progressPercent.value = payload.progress_percent;
        statusMessage.value = payload.message;
        if (payload.stage_latencies) {
          stageLatencies.value = { ...stageLatencies.value, ...payload.stage_latencies };
        }

        if (payload.status === 'ready') {
          stopListening();
          callbacks?.onReady?.(payload);
        } else if (payload.status === 'failed') {
          errorMessage.value = payload.error || 'Error durante la ingestión';
          stopListening();
          callbacks?.onError?.(errorMessage.value);
        }
      } catch (err) {
        console.error('Failed to parse SSE event data', err);
      }
    };

    eventSource.onerror = (err) => {
      console.warn('SSE stream closed or encountered network error', err);
      stopListening();
    };
  }

  function stopListening() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
      isConnected.value = false;
    }
  }

  function reset() {
    stopListening();
    currentStatus.value = null;
    progressPercent.value = 0;
    statusMessage.value = '';
    errorMessage.value = null;
    stageLatencies.value = {};
  }

  return {
    currentStatus,
    progressPercent,
    statusMessage,
    errorMessage,
    stageLatencies,
    isConnected,
    isProcessing,
    isReady,
    isFailed,
    startListening,
    stopListening,
    reset,
  };
}
