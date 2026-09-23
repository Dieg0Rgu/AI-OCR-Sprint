<template>
  <div class="w-full font-mono select-none">
    <!-- Module Header -->
    <div class="flex items-center justify-between border-b border-swiss-border dark:border-swiss-border-dark pb-2 mb-4">
      <span class="text-[11px] font-semibold tracking-wider text-swiss-black dark:text-neutral-200 uppercase">
        [ 01 // INGESTA DE DOCUMENTO ]
      </span>
      <span class="text-[10px] text-swiss-muted">
        FORMATO: PDF / MAX 50 MB
      </span>
    </div>

    <!-- Dropzone Area -->
    <div
      class="relative border border-swiss-border dark:border-swiss-border-dark p-6 transition-all text-center cursor-pointer bg-swiss-surface dark:bg-neutral-900/40 hover:border-swiss-accent hover:bg-swiss-accent/[0.02]"
      :class="{
        'border-swiss-accent bg-swiss-accent/5 ring-1 ring-swiss-accent': isDragging,
        'border-swiss-muted cursor-wait': isUploading,
      }"
      @dragover.prevent="onDragOver"
      @dragleave.prevent="onDragLeave"
      @drop.prevent="onDrop"
      @click="triggerFileInput"
    >
      <input
        ref="fileInputRef"
        type="file"
        accept="application/pdf,.pdf"
        class="hidden"
        @change="onFileSelected"
      />

      <div class="flex flex-col items-center justify-center space-y-3">
        <div class="w-10 h-10 border border-swiss-border dark:border-swiss-border-dark flex items-center justify-center text-swiss-black dark:text-white bg-white dark:bg-swiss-charcoal">
          <span v-if="!isUploading" class="text-sm font-bold">+</span>
          <span v-else class="text-xs animate-spin font-mono">⧗</span>
        </div>

        <div class="space-y-1">
          <p class="text-xs font-semibold text-swiss-black dark:text-neutral-100 uppercase tracking-wide">
            <span class="text-swiss-accent underline underline-offset-2">Seleccionar archivo</span> o arrastrar a esta cuadrícula
          </p>
          <p class="text-[10px] text-swiss-muted">
            Inspección pre-flight automática de integridad binaria (%PDF-)
          </p>
        </div>
      </div>
    </div>

    <!-- Terminal Stepper / Progress Bar (Visible while ingesting or completed) -->
    <div v-if="activeDocumentId || isUploading" class="mt-4 border border-swiss-border dark:border-swiss-border-dark bg-swiss-surface dark:bg-neutral-900 p-3 space-y-3">
      <div class="flex items-center justify-between text-[11px] font-mono">
        <span class="text-swiss-black dark:text-neutral-200 font-bold uppercase">
          ESTADO: {{ (sse.currentStatus.value || 'procesando').toUpperCase() }}
        </span>
        <span class="text-swiss-accent font-bold">
          {{ sse.progressPercent.value }}%
        </span>
      </div>

      <!-- Linear Gauge -->
      <div class="w-full h-1 bg-neutral-200 dark:bg-neutral-800 rounded-none overflow-hidden">
        <div
          class="h-full bg-swiss-accent transition-all duration-300"
          :style="{ width: `${sse.progressPercent.value}%` }"
        ></div>
      </div>

      <!-- Step-by-Step Monospace Terminal -->
      <div class="grid grid-cols-4 gap-1 text-[10px] font-mono text-center pt-1 border-t border-swiss-border dark:border-swiss-border-dark">
        <div
          class="p-1 border"
          :class="isStepActive('uploaded')
            ? 'border-swiss-accent text-swiss-accent font-bold bg-swiss-accent/5'
            : 'border-transparent text-swiss-muted'"
        >
          [01] UPLOADED
        </div>
        <div
          class="p-1 border"
          :class="isStepActive('extracting')
            ? 'border-swiss-accent text-swiss-accent font-bold bg-swiss-accent/5'
            : 'border-transparent text-swiss-muted'"
        >
          [02] EXTRACT
        </div>
        <div
          class="p-1 border"
          :class="isStepActive('indexing')
            ? 'border-swiss-accent text-swiss-accent font-bold bg-swiss-accent/5'
            : 'border-transparent text-swiss-muted'"
        >
          [03] INDEX
        </div>
        <div
          class="p-1 border"
          :class="sse.currentStatus.value === 'ready'
            ? 'border-emerald-500 text-emerald-500 font-bold bg-emerald-500/10'
            : 'border-transparent text-swiss-muted'"
        >
          [04] READY
        </div>
      </div>

      <!-- Live Pipeline Message -->
      <div class="text-[10px] text-swiss-muted flex items-center justify-between pt-1">
        <span class="truncate">{{ sse.statusMessage.value }}</span>
        <span v-if="sse.stageLatencies.value.total_ingestion_time" class="font-mono text-swiss-black dark:text-neutral-200">
          TOTAL: {{ sse.stageLatencies.value.total_ingestion_time.toFixed(2) }}s
        </span>
      </div>
    </div>

    <!-- Diagnostic Error Card with Retry Button -->
    <div
      v-if="uploadError"
      class="mt-4 border border-rose-500/40 bg-rose-500/5 p-4 text-xs font-mono space-y-3"
    >
      <div class="flex items-center justify-between text-rose-500 font-bold tracking-wider">
        <span>[ {{ uploadError.errorCode || 'ERROR_UPLOAD' }} ]</span>
        <button @click="uploadError = null" class="text-rose-400 hover:text-rose-600 text-xs">✕</button>
      </div>
      <p class="text-neutral-700 dark:text-neutral-300 text-[11px] leading-relaxed">
        {{ uploadError.message }}
      </p>
      <div class="pt-2 flex justify-end">
        <button
          @click="retryUpload"
          class="px-3 py-1.5 border border-rose-500 text-rose-500 hover:bg-rose-500 hover:text-white transition-colors text-[10px] font-bold uppercase tracking-wider rounded-none"
        >
          REINTENTAR INGESTA
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ApiService, ApiError } from '../services/api';
import { useDocumentSSE } from '../composables/useDocumentSSE';

const emit = defineEmits<{
  (e: 'document-ready', documentId: string, filename: string): void;
  (e: 'upload-started', documentId: string): void;
}>();

const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragging = ref(false);
const isUploading = ref(false);
const activeDocumentId = ref<string | null>(null);
const lastSelectedFile = ref<File | null>(null);

const uploadError = ref<{ errorCode: string; message: string } | null>(null);

const sse = useDocumentSSE();

function triggerFileInput() {
  if (!isUploading.value) {
    fileInputRef.value?.click();
  }
}

function onDragOver() {
  isDragging.value = true;
}

function onDragLeave() {
  isDragging.value = false;
}

function onDrop(e: DragEvent) {
  isDragging.value = false;
  const files = e.dataTransfer?.files;
  if (files && files.length > 0) {
    processFile(files[0]);
  }
}

function onFileSelected(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    processFile(input.files[0]);
  }
}

async function processFile(file: File) {
  lastSelectedFile.value = file;
  uploadError.value = null;

  // 1. Client-Side Pre-Flight Check (Extension, Size, Magic Bytes)
  const preflight = await ApiService.validatePdfPreflight(file);
  if (!preflight.valid) {
    uploadError.value = {
      errorCode: preflight.errorCode || 'ERROR_VALIDATION',
      message: preflight.message || 'El archivo no pasó la validación inicial.',
    };
    return;
  }

  isUploading.value = true;
  sse.reset();

  try {
    const res = await ApiService.uploadDocument(file);
    activeDocumentId.value = res.document_id;
    emit('upload-started', res.document_id);

    // 2. Start SSE Stream monitoring
    sse.startListening(res.document_id, {
      onReady: () => {
        isUploading.value = false;
        emit('document-ready', res.document_id, res.filename);
      },
      onError: (err) => {
        isUploading.value = false;
        uploadError.value = {
          errorCode: 'ERROR_INGESTION_PIPELINE',
          message: err,
        };
      },
    });
  } catch (err: any) {
    isUploading.value = false;
    if (err instanceof ApiError) {
      uploadError.value = {
        errorCode: err.errorCode,
        message: err.message,
      };
    } else {
      uploadError.value = {
        errorCode: 'ERROR_TRANSFER',
        message: err.message || 'Error de comunicación durante la subida.',
      };
    }
  }
}

function retryUpload() {
  if (lastSelectedFile.value) {
    processFile(lastSelectedFile.value);
  } else {
    triggerFileInput();
  }
}

function isStepActive(step: string): boolean {
  const status = sse.currentStatus.value;
  if (!status) return false;
  if (status === 'ready') return true;
  if (step === 'uploaded') return ['uploaded', 'extracting', 'ocr_processing', 'chunking', 'indexing'].includes(status);
  if (step === 'extracting') return ['extracting', 'ocr_processing', 'chunking', 'indexing'].includes(status);
  if (step === 'indexing') return ['chunking', 'indexing'].includes(status);
  return false;
}
</script>
