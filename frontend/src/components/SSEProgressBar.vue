<template>
  <div class="w-full bg-white dark:bg-swiss-charcoal border border-swiss-border dark:border-swiss-border-dark p-4 font-mono select-none">
    <!-- Header with State and Percentage -->
    <div class="flex items-center justify-between mb-2 text-xs">
      <div class="flex items-center gap-2">
        <span
          class="w-2 h-2 rounded-none inline-block"
          :class="{
            'bg-swiss-accent animate-pulse': isProcessing,
            'bg-emerald-500': isReady,
            'bg-rose-500': isFailed,
            'bg-swiss-muted': !status,
          }"
        ></span>
        <span class="font-bold tracking-wider text-swiss-black dark:text-neutral-100 uppercase">
          {{ stateLabel }}
        </span>
      </div>
      <span class="font-bold text-swiss-accent">
        {{ Math.round(progress) }}%
      </span>
    </div>

    <!-- Progress Bar Track (Flat 2px Swiss Gauge) -->
    <div class="w-full bg-neutral-100 dark:bg-neutral-800 h-1 overflow-hidden rounded-none">
      <div
        class="h-full transition-all duration-300 ease-out"
        :class="{
          'bg-swiss-accent': isProcessing,
          'bg-emerald-500': isReady,
          'bg-rose-500': isFailed,
        }"
        :style="{ width: `${progress}%` }"
      ></div>
    </div>

    <!-- Live Status Message -->
    <p class="text-[11px] text-swiss-muted mt-2 flex items-center justify-between">
      <span class="truncate">{{ message || 'Esperando inicio...' }}</span>
      <span v-if="error" class="text-rose-500 font-bold ml-2">{{ error }}</span>
    </p>

    <!-- Stage Latencies Chips -->
    <div v-if="latencies && Object.keys(latencies).length > 0" class="flex flex-wrap gap-1.5 mt-3 pt-2.5 border-t border-swiss-border dark:border-swiss-border-dark text-[10px]">
      <span
        v-for="(val, key) in latencies"
        :key="key"
        class="inline-flex items-center px-1.5 py-0.5 border border-swiss-border dark:border-swiss-border-dark bg-swiss-surface dark:bg-neutral-900 text-swiss-black dark:text-neutral-300"
      >
        <span class="text-swiss-muted mr-1">{{ formatStageName(key) }}: </span>
        <span class="font-bold text-swiss-accent">{{ val }}s</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { DocumentStatus } from '../types';

const props = defineProps<{
  status: DocumentStatus | null;
  progress: number;
  message: string;
  error?: string | null;
  latencies?: Record<string, number>;
}>();

const isProcessing = computed(
  () => props.status && props.status !== 'ready' && props.status !== 'failed'
);
const isReady = computed(() => props.status === 'ready');
const isFailed = computed(() => props.status === 'failed');

const stateLabel = computed(() => {
  switch (props.status) {
    case 'uploaded':
      return '1. Subido & Validado';
    case 'extracting':
      return '2. Extracción PyMuPDF';
    case 'ocr_processing':
      return '3. OCR de Respaldo';
    case 'chunking':
      return '4. Segmentación Semántica';
    case 'indexing':
      return '5. Indexación Qdrant + BM25';
    case 'ready':
      return '✓ Listo para Consultas';
    case 'failed':
      return '✕ Error en Ingestión';
    default:
      return 'En espera';
  }
});

function formatStageName(key: string): string {
  const map: Record<string, string> = {
    extraction_time: 'Extracción',
    ocr_time: 'OCR',
    chunking_time: 'Chunking',
    embedding_time: 'Embeddings',
    indexing_time: 'Indexación',
    total_ingestion_time: 'Total',
  };
  return map[key] || key;
}
</script>
