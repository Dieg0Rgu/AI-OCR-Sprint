<template>
  <div class="h-full flex flex-col bg-white dark:bg-swiss-charcoal border-l border-swiss-border dark:border-swiss-border-dark select-none">
    <!-- Technical Module Header -->
    <div class="h-12 border-b border-swiss-border dark:border-swiss-border-dark px-4 flex items-center justify-between bg-swiss-surface dark:bg-neutral-900/60">
      <div class="flex items-center gap-2">
        <span class="text-[11px] font-mono font-semibold tracking-wider text-swiss-black dark:text-neutral-200 uppercase">
          [ 02 // BÚSQUEDA LÉXICA ]
        </span>
      </div>
      <div class="flex items-center gap-1.5 font-mono text-[10px] text-swiss-muted">
        <kbd class="px-1.5 py-0.5 border border-swiss-border dark:border-swiss-border-dark bg-white dark:bg-neutral-800 rounded-sm">
          ⌘K
        </kbd>
        <span>O</span>
        <kbd class="px-1.5 py-0.5 border border-swiss-border dark:border-swiss-border-dark bg-white dark:bg-neutral-800 rounded-sm">
          Ctrl+K
        </kbd>
      </div>
    </div>

    <!-- Search Input & Filters Toolbar -->
    <div class="p-3 border-b border-swiss-border dark:border-swiss-border-dark bg-white dark:bg-swiss-charcoal space-y-2">
      <div class="relative flex items-center">
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          type="text"
          placeholder="Buscar palabra o frase en el documento..."
          class="w-full h-9 pl-3 pr-20 text-xs font-mono bg-swiss-surface dark:bg-neutral-900 border border-swiss-border dark:border-swiss-border-dark rounded-sm text-swiss-black dark:text-neutral-100 placeholder:text-swiss-muted focus:outline-none focus:border-swiss-accent focus:ring-1 focus:ring-swiss-accent"
          @keydown.enter.prevent="nextMatch"
        />

        <!-- Filter Toggles inside search bar -->
        <div class="absolute right-1.5 flex items-center gap-1">
          <button
            type="button"
            @click="toggleCaseSensitive"
            class="px-1.5 py-0.5 text-[10px] font-mono rounded-sm transition-colors"
            :class="caseSensitive
              ? 'bg-swiss-accent text-white font-bold'
              : 'text-swiss-muted hover:text-swiss-black dark:hover:text-white'"
            title="Distinguir mayúsculas / minúsculas"
          >
            Aa
          </button>
          <button
            type="button"
            @click="toggleExactMatch"
            class="px-1.5 py-0.5 text-[10px] font-mono rounded-sm transition-colors"
            :class="exactMatch
              ? 'bg-swiss-accent text-white font-bold'
              : 'text-swiss-muted hover:text-swiss-black dark:hover:text-white'"
            title="Palabra completa exacta"
          >
            " "
          </button>
        </div>
      </div>

      <!-- Navigation & Match Counter Subheader -->
      <div class="flex items-center justify-between text-[11px] font-mono text-swiss-muted px-1">
        <div v-if="searchQuery.trim()">
          <span v-if="isSearching" class="text-swiss-muted animate-pulse">
            Buscando coincidencias...
          </span>
          <span v-else-if="matches.length > 0" class="text-swiss-black dark:text-neutral-200">
            [ COINCIDENCIA {{ activeIndex + 1 }} / {{ matches.length }} //
            <span class="text-swiss-accent font-bold">PÁG. {{ String(currentMatch?.page_number || 0).padStart(2, '0') }}</span> ]
          </span>
          <span v-else class="text-swiss-muted">
            0 coincidencias encontradas
          </span>
        </div>
        <div v-else class="text-swiss-muted">
          Escribe para indexar ocurrencias
        </div>

        <!-- Stepper Buttons -->
        <div v-if="matches.length > 0" class="flex items-center gap-1">
          <button
            @click="prevMatch"
            class="px-2 py-0.5 text-xs font-mono border border-swiss-border dark:border-swiss-border-dark rounded-sm hover:bg-swiss-surface dark:hover:bg-neutral-800 text-swiss-black dark:text-neutral-200 transition-colors"
            title="Coincidencia anterior"
          >
            ↑
          </button>
          <button
            @click="nextMatch"
            class="px-2 py-0.5 text-xs font-mono border border-swiss-border dark:border-swiss-border-dark rounded-sm hover:bg-swiss-surface dark:hover:bg-neutral-800 text-swiss-black dark:text-neutral-200 transition-colors"
            title="Siguiente coincidencia"
          >
            ↓
          </button>
        </div>
      </div>
    </div>

    <!-- Editorial Results Index -->
    <div class="flex-1 overflow-y-auto divide-y divide-swiss-border dark:divide-swiss-border-dark bg-white dark:bg-swiss-charcoal">
      <!-- Empty State -->
      <div
        v-if="!searchQuery.trim()"
        class="h-full flex flex-col items-center justify-center p-8 text-center text-swiss-muted font-mono"
      >
        <div class="w-8 h-8 border border-swiss-border dark:border-swiss-border-dark flex items-center justify-center text-xs mb-3 text-swiss-black dark:text-white">
          §
        </div>
        <p class="text-xs font-semibold uppercase tracking-wider text-swiss-black dark:text-neutral-300">
          Índice Analítico Léxico
        </p>
        <p class="text-[11px] mt-1 max-w-[240px] leading-relaxed">
          Localiza al instante cualquier término técnico en el documento con coordenadas de página.
        </p>
      </div>

      <!-- No Results State -->
      <div
        v-else-if="!isSearching && matches.length === 0"
        class="p-6 text-center text-swiss-muted font-mono text-xs"
      >
        No se encontraron coincidencias para "{{ searchQuery }}".
      </div>

      <!-- Match Rows List -->
      <div
        v-for="(match, idx) in matches"
        :key="match.match_id"
        @click="selectMatch(idx)"
        class="p-3 text-left transition-colors cursor-pointer group"
        :class="activeIndex === idx
          ? 'bg-swiss-accent/5 dark:bg-swiss-accent/10 border-l-2 border-swiss-accent'
          : 'hover:bg-swiss-surface dark:hover:bg-neutral-900/60'"
      >
        <div class="flex items-center justify-between text-[10px] font-mono text-swiss-muted mb-1">
          <span
            class="px-1.5 py-0.5 border rounded-sm font-semibold tracking-wider"
            :class="activeIndex === idx
              ? 'border-swiss-accent text-swiss-accent bg-swiss-accent/10'
              : 'border-swiss-border dark:border-swiss-border-dark text-swiss-black dark:text-neutral-300'"
          >
            PÁG. {{ String(match.page_number).padStart(2, '0') }}
          </span>
          <span v-if="match.line_number" class="text-swiss-muted">
            LÍNEA {{ match.line_number }}
          </span>
        </div>

        <!-- Highlighted Editorial Snippet -->
        <p class="text-xs leading-relaxed text-swiss-black dark:text-neutral-200 font-sans" v-html="formatSnippet(match.snippet)"></p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import type { KeywordSearchMatch } from '../types';
import { ApiService } from '../services/api';

const props = defineProps<{
  documentId: string | null;
}>();

const emit = defineEmits<{
  (e: 'jump-to-match', payload: { pageNumber: number; bbox: number[] | null }): void;
}>();

const searchInputRef = ref<HTMLInputElement | null>(null);
const searchQuery = ref('');
const caseSensitive = ref(false);
const exactMatch = ref(false);

const matches = ref<KeywordSearchMatch[]>([]);
const activeIndex = ref<number>(0);
const isSearching = ref(false);

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

const currentMatch = computed(() => {
  if (matches.value.length === 0) return null;
  return matches.value[activeIndex.value] || null;
});

function toggleCaseSensitive() {
  caseSensitive.value = !caseSensitive.value;
  triggerSearch();
}

function toggleExactMatch() {
  exactMatch.value = !exactMatch.value;
  triggerSearch();
}

function triggerSearch() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    executeSearch();
  }, 250);
}

async function executeSearch() {
  if (!props.documentId || !searchQuery.value.trim()) {
    matches.value = [];
    activeIndex.value = 0;
    return;
  }

  isSearching.value = true;
  try {
    const res = await ApiService.searchDocumentKeywords(
      props.documentId,
      searchQuery.value.trim(),
      caseSensitive.value,
      exactMatch.value
    );
    matches.value = res.matches;
    activeIndex.value = 0;

    if (matches.value.length > 0) {
      notifyMatch(0);
    }
  } catch (err) {
    console.error('Keyword search failed', err);
    matches.value = [];
  } finally {
    isSearching.value = false;
  }
}

function selectMatch(index: number) {
  if (index >= 0 && index < matches.value.length) {
    activeIndex.value = index;
    notifyMatch(index);
  }
}

function nextMatch() {
  if (matches.value.length === 0) return;
  const nextIdx = (activeIndex.value + 1) % matches.value.length;
  selectMatch(nextIdx);
}

function prevMatch() {
  if (matches.value.length === 0) return;
  const prevIdx = (activeIndex.value - 1 + matches.value.length) % matches.value.length;
  selectMatch(prevIdx);
}

function notifyMatch(idx: number) {
  const match = matches.value[idx];
  if (match) {
    emit('jump-to-match', {
      pageNumber: match.page_number,
      bbox: match.bbox,
    });
  }
}

function formatSnippet(snippet: string): string {
  // Replace **keyword** with Swiss Accent span
  return snippet.replace(
    /\*\*(.*?)\*\*/g,
    '<mark class="bg-swiss-accent/20 text-swiss-accent font-semibold px-1 py-0.5 rounded-none border-b border-swiss-accent">$1</mark>'
  );
}

function focusInput() {
  searchInputRef.value?.focus();
  searchInputRef.value?.select();
}

// Global Keyboard Shortcut: Cmd+K / Ctrl+K
function handleKeyDown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    focusInput();
  }
}

watch(searchQuery, () => {
  triggerSearch();
});

watch(
  () => props.documentId,
  () => {
    searchQuery.value = '';
    matches.value = [];
    activeIndex.value = 0;
  }
);

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
  if (debounceTimer) clearTimeout(debounceTimer);
});

defineExpose({
  focusInput,
  nextMatch,
  prevMatch,
});
</script>
