<template>
  <div class="border-t border-swiss-border dark:border-swiss-border-dark bg-white dark:bg-swiss-charcoal select-none transition-all duration-300 flex flex-col font-mono">
    <!-- Technical Drawer Header Bar (always visible) -->
    <div
      class="h-10 px-4 bg-swiss-surface dark:bg-neutral-900/80 border-b border-swiss-border dark:border-swiss-border-dark flex items-center justify-between text-xs cursor-pointer hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
      @click="isExpanded = !isExpanded"
    >
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 bg-swiss-accent rounded-none inline-block"></span>
        <span class="font-bold text-swiss-black dark:text-neutral-100 uppercase tracking-wider text-[11px]">
          [ 01 // GALERÍA DE FIGURAS INDEXADAS ]
        </span>
        <span class="text-swiss-accent font-bold text-[11px]">
          [{{ filteredImages.length }} / {{ images.length }}]
        </span>
      </div>

      <div class="flex items-center gap-3">
        <span class="text-[10px] text-swiss-muted hidden sm:inline">
          {{ isExpanded ? 'CLICK PARA COLAPSAR' : 'CLICK PARA EXPANDIR' }}
        </span>
        <button
          type="button"
          class="px-2 py-0.5 border border-swiss-border dark:border-swiss-border-dark text-[10px] uppercase font-bold text-swiss-black dark:text-neutral-200 bg-white dark:bg-neutral-800 hover:border-swiss-accent transition-colors"
        >
          {{ isExpanded ? '▼ OCULTAR' : '▲ MOSTRAR' }}
        </button>
      </div>
    </div>

    <!-- Expanded Drawer Content -->
    <div
      v-if="isExpanded"
      class="h-64 sm:h-72 flex flex-col bg-white dark:bg-swiss-charcoal overflow-hidden"
    >
      <!-- Sub-toolbar: Filter by Page or Keyword -->
      <div class="px-4 py-2 border-b border-swiss-border dark:border-swiss-border-dark bg-white dark:bg-swiss-charcoal flex items-center gap-3 text-xs">
        <div class="flex-1 relative flex items-center">
          <input
            v-model="filterQuery"
            type="text"
            placeholder="Filtrar figuras por página (ej. 3) o término en pie de figura..."
            class="w-full h-8 pl-3 pr-8 text-[11px] font-mono bg-swiss-surface dark:bg-neutral-900 border border-swiss-border dark:border-swiss-border-dark rounded-none text-swiss-black dark:text-neutral-100 placeholder:text-swiss-muted focus:outline-none focus:border-swiss-accent focus:ring-1 focus:ring-swiss-accent"
          />
          <button
            v-if="filterQuery"
            @click="filterQuery = ''"
            class="absolute right-2 text-swiss-muted hover:text-swiss-black dark:hover:text-white text-[11px]"
          >
            ✕
          </button>
        </div>

        <div class="flex items-center gap-1.5 text-[10px] text-swiss-muted whitespace-nowrap">
          <span>ORDEN: PÁGINA ASCENDENTE</span>
        </div>
      </div>

      <!-- Figures Horizontal Scrolling Grid -->
      <div class="flex-1 overflow-x-auto overflow-y-hidden p-3 flex gap-3">
        <!-- Empty State -->
        <div
          v-if="filteredImages.length === 0"
          class="w-full h-full flex flex-col items-center justify-center text-swiss-muted text-xs text-center p-4"
        >
          <span class="text-sm font-bold text-swiss-black dark:text-neutral-200 mb-1">
            0 FIGURAS ENCONTRADAS
          </span>
          <p class="text-[11px]">
            {{ filterQuery ? `Sin coincidencias para "${filterQuery}".` : 'Este documento no contiene imágenes rasterizadas o diagramas detectados.' }}
          </p>
        </div>

        <!-- Figure Card -->
        <div
          v-for="(img, idx) in filteredImages"
          :key="img.image_id"
          class="flex-shrink-0 w-64 border border-swiss-border dark:border-swiss-border-dark bg-swiss-surface dark:bg-neutral-900 flex flex-col justify-between p-2.5 transition-all hover:border-swiss-accent group rounded-none"
        >
          <!-- Card Header: ID & Page Badge -->
          <div class="flex items-center justify-between text-[10px] font-mono pb-1.5 border-b border-swiss-border dark:border-swiss-border-dark">
            <span class="font-bold text-swiss-black dark:text-neutral-200 uppercase">
              #IMG_{{ String(img.order || idx + 1).padStart(2, '0') }}
            </span>
            <span class="px-1.5 py-0.2 bg-white dark:bg-neutral-800 border border-swiss-border dark:border-swiss-border-dark text-swiss-accent font-bold">
              [ PÁG. {{ String(img.page_number).padStart(2, '0') }} ]
            </span>
          </div>

          <!-- Thumbnail Area -->
          <div
            class="my-2 h-24 bg-white dark:bg-neutral-950 border border-swiss-border dark:border-swiss-border-dark flex items-center justify-center p-1.5 overflow-hidden relative cursor-pointer"
            @click="$emit('inspect-figure', img)"
            title="Inspeccionar figura con Moondream"
          >
            <img
              :src="img.url"
              :alt="img.image_id"
              class="max-h-full max-w-full object-contain transition-transform group-hover:scale-105"
            />
            <span class="absolute bottom-1 right-1 text-[9px] bg-black/75 text-white px-1 py-0.2 font-mono">
              {{ img.width }}x{{ img.height }}
            </span>
          </div>

          <!-- Caption & Context Summary -->
          <div class="text-[10px] leading-tight text-swiss-black dark:text-neutral-300 font-sans mb-2 h-8 overflow-hidden line-clamp-2">
            <span v-if="img.caption" class="font-semibold text-swiss-accent">
              {{ img.caption }}
            </span>
            <span v-else-if="img.section_title" class="text-swiss-muted">
              {{ img.section_title }}
            </span>
            <span v-else class="text-swiss-muted italic">
              Figura sin pie de foto explícito en pág. {{ img.page_number }}.
            </span>
          </div>

          <!-- Action Buttons -->
          <div class="grid grid-cols-2 gap-1.5 pt-1.5 border-t border-swiss-border dark:border-swiss-border-dark font-mono text-[9px]">
            <button
              @click="$emit('jump-to-figure', { pageNumber: img.page_number, bbox: img.bbox })"
              class="px-1.5 py-1 border border-swiss-border dark:border-swiss-border-dark bg-white dark:bg-neutral-800 hover:border-swiss-accent hover:text-swiss-accent transition-colors font-bold uppercase truncate"
              title="Saltar a esta página en el visor"
            >
              IR A PÁG. {{ img.page_number }}
            </button>
            <button
              @click="$emit('inspect-figure', img)"
              class="px-1.5 py-1 bg-swiss-accent hover:bg-blue-700 text-white font-bold uppercase transition-colors truncate"
              title="Analizar figura con Moondream"
            >
              MOONDREAM
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { ExtractedImageMetadata } from '../types';

const props = defineProps<{
  images: ExtractedImageMetadata[];
}>();

defineEmits<{
  (e: 'jump-to-figure', payload: { pageNumber: number; bbox: number[] | null }): void;
  (e: 'inspect-figure', image: ExtractedImageMetadata): void;
}>();

const isExpanded = ref(true);
const filterQuery = ref('');

const sortedImages = computed(() => {
  return [...props.images].sort((a, b) => {
    if (a.page_number !== b.page_number) {
      return a.page_number - b.page_number;
    }
    return (a.order || 0) - (b.order || 0);
  });
});

const filteredImages = computed(() => {
  const q = filterQuery.value.trim().toLowerCase();
  if (!q) return sortedImages.value;

  const pageNum = parseInt(q, 10);
  return sortedImages.value.filter((img) => {
    if (!isNaN(pageNum) && img.page_number === pageNum) {
      return true;
    }
    const captionMatch = img.caption?.toLowerCase().includes(q);
    const sectionMatch = img.section_title?.toLowerCase().includes(q);
    const textMatch = img.surrounding_text?.toLowerCase().includes(q);
    const idMatch = img.image_id.toLowerCase().includes(q);
    return captionMatch || sectionMatch || textMatch || idMatch;
  });
});

defineExpose({
  isExpanded,
  toggleExpand: () => {
    isExpanded.value = !isExpanded.value;
  },
});
</script>
