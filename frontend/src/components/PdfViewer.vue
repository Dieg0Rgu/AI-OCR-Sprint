<template>
  <div class="h-full flex flex-col bg-neutral-100 dark:bg-neutral-950 border border-swiss-border dark:border-swiss-border-dark select-none">
    <!-- 48px Fixed Technical Toolbar -->
    <div class="h-12 bg-white dark:bg-swiss-charcoal border-b border-swiss-border dark:border-swiss-border-dark px-4 flex items-center justify-between font-mono text-xs">
      <div class="flex items-center gap-2">
        <span class="font-bold tracking-wider text-swiss-black dark:text-neutral-100 uppercase">
          [ 00 // VISOR DOCUMENTAL ]
        </span>
        <span
          v-if="highlightActive && activeBbox"
          class="text-[10px] px-2 py-0.5 border border-swiss-accent text-swiss-accent bg-swiss-accent/5 font-semibold tracking-wider uppercase"
        >
          [ CITA RESALTADA ]
        </span>
      </div>

      <!-- Controls: Pagination & Zoom -->
      <div class="flex items-center gap-3">
        <!-- Pagination Stepper -->
        <div class="flex items-center border border-swiss-border dark:border-swiss-border-dark bg-swiss-surface dark:bg-neutral-900 px-1 py-0.5">
          <button
            @click="prevPage"
            :disabled="currentPage <= 1"
            class="px-2 py-1 text-xs hover:text-swiss-accent disabled:opacity-30 disabled:hover:text-inherit font-bold"
            title="Página Anterior"
          >
            ‹
          </button>
          <span class="px-2 font-mono text-swiss-black dark:text-neutral-200 text-[11px]">
            PÁG. {{ String(currentPage).padStart(2, '0') }} / {{ String(totalPages || 1).padStart(2, '0') }}
          </span>
          <button
            @click="nextPage"
            :disabled="currentPage >= totalPages"
            class="px-2 py-1 text-xs hover:text-swiss-accent disabled:opacity-30 disabled:hover:text-inherit font-bold"
            title="Página Siguiente"
          >
            ›
          </button>
        </div>

        <!-- Zoom Controls -->
        <div class="flex items-center border border-swiss-border dark:border-swiss-border-dark bg-swiss-surface dark:bg-neutral-900 px-1 py-0.5">
          <button
            @click="zoomOut"
            class="px-2 py-1 text-xs hover:text-swiss-accent font-mono font-bold"
            title="Reducir"
          >
            -
          </button>
          <span class="px-2 text-swiss-muted text-[11px]">
            {{ Math.round(zoomLevel * 100) }}%
          </span>
          <button
            @click="zoomIn"
            class="px-2 py-1 text-xs hover:text-swiss-accent font-mono font-bold"
            title="Aumentar"
          >
            +
          </button>
          <button
            @click="resetZoom"
            class="ml-1 px-1.5 py-0.5 text-[10px] border-l border-swiss-border dark:border-swiss-border-dark hover:text-swiss-accent text-swiss-muted"
            title="Restablecer a 100%"
          >
            1:1
          </button>
        </div>
      </div>
    </div>

    <!-- Viewer Body -->
    <div
      ref="containerRef"
      class="flex-1 overflow-auto p-6 flex items-start justify-center relative scroll-smooth bg-neutral-200/50 dark:bg-neutral-900/50"
    >
      <!-- Empty Document State -->
      <div v-if="!pdfUrl" class="h-full flex flex-col items-center justify-center text-swiss-muted font-mono text-xs text-center p-8">
        <div class="w-10 h-10 border border-swiss-border dark:border-swiss-border-dark flex items-center justify-center mb-3 text-swiss-black dark:text-white">
          PDF
        </div>
        <p class="font-semibold uppercase tracking-wider text-swiss-black dark:text-neutral-300">
          Ningún documento activo
        </p>
        <p class="text-[11px] mt-1 max-w-[240px]">
          Carga un archivo PDF para iniciar la renderización y visualización vectorial.
        </p>
      </div>

      <!-- PDF Canvas Layer with Precision Highlight Overlay -->
      <div
        v-show="pdfUrl"
        class="relative border border-swiss-border dark:border-swiss-border-dark bg-white transition-transform duration-100 origin-top shadow-sm"
        :style="{ transform: `scale(${zoomLevel})` }"
      >
        <canvas ref="canvasRef" class="block max-w-none"></canvas>

        <!-- Coordinate-Aware Precision BBox Highlight -->
        <div
          v-if="highlightActive && bboxStyle"
          class="absolute border-2 border-swiss-accent bg-swiss-accent/15 pointer-events-none transition-all duration-300 animate-pulse"
          :style="bboxStyle"
        >
          <div class="absolute -top-5 left-0 px-1 py-0.5 bg-swiss-accent text-white text-[9px] font-mono font-bold uppercase tracking-wider">
            [ COORDENADA SELECCIONADA ]
          </div>
        </div>

        <!-- Full-Page Flash Highlight Fallback -->
        <div
          v-else-if="highlightActive && !bboxStyle"
          class="absolute inset-0 pointer-events-none border-2 border-swiss-accent bg-swiss-accent/5 transition-all"
        >
          <div class="absolute top-3 right-3 bg-swiss-accent text-white font-mono font-bold text-[10px] px-2 py-0.5 uppercase tracking-wider">
            PÁGINA {{ currentPage }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue';

const props = defineProps<{
  pdfUrl: string | null;
  initialPage?: number;
  highlightPage?: number | null;
  highlightBbox?: number[] | null;
}>();

const containerRef = ref<HTMLDivElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);

const currentPage = ref<number>(props.initialPage || 1);
const totalPages = ref<number>(1);
const zoomLevel = ref<number>(1.0);
const activeBbox = ref<number[] | null>(null);
const highlightActive = ref<boolean>(false);

const pageWidthPoints = ref<number>(595);
const pageHeightPoints = ref<number>(842);

let pdfDoc: any = null;

const bboxStyle = computed(() => {
  if (!activeBbox.value || activeBbox.value.length < 4) return null;
  const [x0, y0, x1, y1] = activeBbox.value;

  const pw = pageWidthPoints.value || 595;
  const ph = pageHeightPoints.value || 842;

  const left = Math.max(0, (x0 / pw) * 100);
  const top = Math.max(0, (y0 / ph) * 100);
  const width = Math.min(100 - left, ((x1 - x0) / pw) * 100);
  const height = Math.min(100 - top, ((y1 - y0) / ph) * 100);

  return {
    left: `${left}%`,
    top: `${top}%`,
    width: `${width}%`,
    height: `${height}%`,
  };
});

async function initPdf(url: string) {
  try {
    const pdfjsLib = await import('pdfjs-dist');
    pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

    const loadingTask = pdfjsLib.getDocument(url);
    pdfDoc = await loadingTask.promise;
    totalPages.value = pdfDoc.numPages;
    await renderPage(currentPage.value);
  } catch (err) {
    console.error('Failed to load PDF via pdfjs-dist', err);
  }
}

async function renderPage(pageNum: number) {
  if (!pdfDoc || !canvasRef.value) return;

  try {
    const page = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: 1.5 });
    const canvas = canvasRef.value;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    pageWidthPoints.value = page.view[2] || 595;
    pageHeightPoints.value = page.view[3] || 842;

    canvas.height = viewport.height;
    canvas.width = viewport.width;

    const renderContext = {
      canvasContext: ctx,
      viewport: viewport,
    };

    await page.render(renderContext).promise;
  } catch (err) {
    console.error('Error rendering PDF page', err);
  }
}

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--;
    highlightActive.value = false;
    renderPage(currentPage.value);
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
    highlightActive.value = false;
    renderPage(currentPage.value);
  }
}

function zoomIn() {
  if (zoomLevel.value < 2.5) {
    zoomLevel.value = Math.round((zoomLevel.value + 0.15) * 100) / 100;
  }
}

function zoomOut() {
  if (zoomLevel.value > 0.5) {
    zoomLevel.value = Math.round((zoomLevel.value - 0.15) * 100) / 100;
  }
}

function resetZoom() {
  zoomLevel.value = 1.0;
}

function goToPage(pageNum: number, bbox: number[] | null = null) {
  if (pageNum >= 1 && pageNum <= totalPages.value) {
    currentPage.value = pageNum;
    activeBbox.value = bbox;
    highlightActive.value = true;
    renderPage(pageNum);

    nextTick(() => {
      if (bbox && containerRef.value) {
        // Scroll proportionally towards bbox vertical coordinate
        const topRatio = bbox[1] / (pageHeightPoints.value || 842);
        const targetScroll = containerRef.value.scrollHeight * topRatio - 100;
        containerRef.value.scrollTo({ top: Math.max(0, targetScroll), behavior: 'smooth' });
      } else {
        containerRef.value?.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });

    // Keep highlight active for 5 seconds
    setTimeout(() => {
      highlightActive.value = false;
    }, 5000);
  }
}

defineExpose({
  goToPage,
  nextPage,
  prevPage,
  zoomIn,
  zoomOut,
  resetZoom,
  currentPage,
  totalPages,
});

watch(
  () => props.pdfUrl,
  (newUrl) => {
    if (newUrl) {
      currentPage.value = 1;
      initPdf(newUrl);
    }
  },
  { immediate: true }
);

watch(
  () => props.highlightPage,
  (newPage) => {
    if (newPage) {
      goToPage(newPage, props.highlightBbox || null);
    }
  }
);
</script>
