<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm select-none font-mono"
    @click.self="close"
  >
    <div
      class="w-full max-w-4xl max-h-[90vh] bg-white dark:bg-swiss-charcoal border border-swiss-border dark:border-swiss-border-dark shadow-2xl flex flex-col overflow-hidden"
    >
      <!-- Modal Header -->
      <div class="h-12 bg-swiss-surface dark:bg-neutral-900 border-b border-swiss-border dark:border-swiss-border-dark px-4 flex items-center justify-between text-xs">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 bg-swiss-accent rounded-none inline-block"></span>
          <h2 class="font-bold text-swiss-black dark:text-neutral-100 uppercase tracking-wider">
            [ 04 // INSPECCIÓN VISUAL DE FIGURAS · LLAVA 7B ]
          </h2>
        </div>
        <button
          @click="close"
          class="text-swiss-muted hover:text-swiss-black dark:hover:text-white px-2 py-1 border border-transparent hover:border-swiss-border dark:hover:border-swiss-border-dark transition-colors uppercase text-[11px]"
        >
          [ CERRAR ✕ ]
        </button>
      </div>

      <!-- Modal Body -->
      <div class="flex-1 overflow-y-auto p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Left: Image Preview & Gallery -->
        <div class="space-y-3 flex flex-col">
          <!-- Active Preview -->
          <div class="flex-1 min-h-[260px] bg-swiss-surface dark:bg-neutral-900/60 border border-swiss-border dark:border-swiss-border-dark p-3 flex items-center justify-center relative overflow-hidden group">
            <img
              v-if="selectedImage"
              :src="selectedImage.url"
              :alt="selectedImage.image_id"
              class="max-h-[300px] w-auto object-contain rounded-none border border-swiss-border dark:border-swiss-border-dark shadow-sm bg-white"
            />
            <div v-else class="text-swiss-muted text-xs">
              No hay figuras seleccionadas
            </div>

            <!-- Page Badge -->
            <span
              v-if="selectedImage"
              class="absolute bottom-2 left-2 text-[10px] bg-white dark:bg-swiss-charcoal text-swiss-black dark:text-neutral-200 px-2 py-0.5 border border-swiss-border dark:border-swiss-border-dark font-mono font-bold uppercase"
            >
              PÁG. {{ selectedImage.page_number }} | {{ selectedImage.width }}x{{ selectedImage.height }} PX
            </span>
          </div>

          <!-- Thumbnails Gallery -->
          <div class="space-y-1.5">
            <span class="text-[10px] font-bold text-swiss-muted uppercase tracking-wider block">
              FIGURAS EXTRAÍDAS ({{ images.length }}):
            </span>
            <div class="flex gap-2 overflow-x-auto pb-1">
              <button
                v-for="img in images"
                :key="img.image_id"
                @click="selectedImage = img"
                class="flex-shrink-0 w-16 h-16 border rounded-none p-0.5 transition-all bg-white dark:bg-neutral-800"
                :class="selectedImage?.image_id === img.image_id
                  ? 'border-swiss-accent ring-1 ring-swiss-accent'
                  : 'border-swiss-border dark:border-swiss-border-dark opacity-60 hover:opacity-100'"
              >
                <img :src="img.url" class="w-full h-full object-cover rounded-none" />
              </button>
            </div>
          </div>
        </div>

        <!-- Right: Vision Prompt & Analysis -->
        <div class="flex flex-col space-y-3">
          <!-- Prompt Formulation -->
          <div class="space-y-1.5">
            <label class="text-[10px] font-bold uppercase tracking-wider text-swiss-muted">
              CONSULTA A LLAVA 7B:
            </label>
            <div class="flex gap-2">
              <input
                v-model="visionPrompt"
                type="text"
                placeholder="Describe la tendencia o métrica clave en este gráfico..."
                :disabled="isAnalyzing || !selectedImage"
                class="flex-1 h-9 px-3 text-xs font-sans bg-swiss-surface dark:bg-neutral-900 border border-swiss-border dark:border-swiss-border-dark rounded-none text-swiss-black dark:text-neutral-100 placeholder:text-swiss-muted focus:outline-none focus:border-swiss-accent focus:ring-1 focus:ring-swiss-accent disabled:opacity-40"
                @keyup.enter="handleAnalyze"
              />
              <button
                @click="handleAnalyze"
                :disabled="!visionPrompt.trim() || isAnalyzing || !selectedImage"
                class="px-4 h-9 bg-swiss-accent hover:bg-blue-700 disabled:bg-neutral-300 dark:disabled:bg-neutral-800 disabled:text-neutral-500 text-white rounded-none text-xs font-mono font-bold tracking-wider uppercase transition-colors flex items-center gap-1.5"
              >
                <span v-if="!isAnalyzing">ANALIZAR</span>
                <span v-else class="animate-spin">⧗</span>
              </button>
            </div>
          </div>

          <!-- Numerical Estimation Warning Alert -->
          <div
            v-if="analysisResult?.has_numerical_estimates"
            class="p-3 border border-amber-500/50 bg-amber-500/5 text-amber-600 dark:text-amber-400 text-xs space-y-1"
          >
            <div class="font-bold uppercase tracking-wider text-[10px] flex items-center gap-1.5">
              <span>⚠</span>
              <span>ADVERTENCIA DE ESTIMACIÓN VISUAL NUMÉRICA</span>
            </div>
            <p class="text-[11px] leading-relaxed font-sans text-neutral-800 dark:text-neutral-200">
              {{ analysisResult.estimation_warning }}
            </p>
          </div>

          <!-- Analysis Response Body -->
          <div class="flex-1 bg-swiss-surface dark:bg-neutral-900/60 border border-swiss-border dark:border-swiss-border-dark p-4 overflow-y-auto min-h-[160px] text-xs leading-relaxed text-swiss-black dark:text-neutral-200 font-sans">
            <div v-if="isAnalyzing" class="h-full flex flex-col items-center justify-center text-swiss-muted font-mono gap-2 text-xs">
              <span class="inline-block w-3 h-3 bg-swiss-accent animate-ping"></span>
              <span class="uppercase tracking-wider text-[10px]">[ RAZONANDO CON LLAVA 7B... ]</span>
            </div>
            <div v-else-if="analysisResult">
              {{ analysisResult.analysis }}
            </div>
            <div v-else class="h-full flex items-center justify-center text-swiss-muted text-center font-mono text-[11px]">
              Selecciona una figura y ejecuta la consulta para inspección visual.
            </div>
          </div>

          <!-- Latency Metrics Footer -->
          <div v-if="analysisResult?.metrics" class="text-[10px] font-mono text-swiss-muted flex justify-end gap-3 pt-1 border-t border-swiss-border dark:border-swiss-border-dark">
            <span>VISIÓN: {{ Math.round((analysisResult.metrics.vision_time || 0) * 1000) }}ms</span>
            <span class="text-swiss-accent font-bold">TOTAL: {{ Math.round((analysisResult.metrics.total_time || 0) * 1000) }}ms</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import type { ExtractedImageMetadata, VisionQueryResponse } from '../types';
import { ApiService } from '../services/api';

const props = defineProps<{
  isOpen: boolean;
  documentId: string | null;
  images: ExtractedImageMetadata[];
  initialImageId?: string | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const selectedImage = ref<ExtractedImageMetadata | null>(null);
const visionPrompt = ref('');
const isAnalyzing = ref(false);
const analysisResult = ref<VisionQueryResponse | null>(null);

function close() {
  emit('close');
}

async function handleAnalyze() {
  if (!props.documentId || !selectedImage.value || !visionPrompt.value.trim() || isAnalyzing.value) {
    return;
  }

  isAnalyzing.value = true;
  analysisResult.value = null;

  try {
    const res = await ApiService.queryVision(
      props.documentId,
      selectedImage.value.image_id,
      visionPrompt.value.trim()
    );
    analysisResult.value = res;
  } catch (err: any) {
    analysisResult.value = {
      image_id: selectedImage.value.image_id,
      analysis: `[ERROR] ${err.message || 'Fallo en la inferencia multimodal'}`,
      has_numerical_estimates: false,
      metrics: {},
    };
  } finally {
    isAnalyzing.value = false;
  }
}

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      if (props.initialImageId) {
        selectedImage.value = props.images.find(i => i.image_id === props.initialImageId) || props.images[0] || null;
      } else if (!selectedImage.value && props.images.length > 0) {
        selectedImage.value = props.images[0];
      }
      visionPrompt.value = 'Interpreta esta figura y describe los datos o patrones clave.';
    } else {
      analysisResult.value = null;
    }
  }
);
</script>
