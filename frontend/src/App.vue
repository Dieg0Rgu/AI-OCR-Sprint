<template>
  <div class="h-full flex flex-col bg-white dark:bg-swiss-charcoal text-swiss-black dark:text-neutral-100 font-sans selection:bg-swiss-accent selection:text-white">
    <!-- Top Utility Bar: 48px (h-12) Swiss Editorial Grid -->
    <header class="h-12 border-b border-swiss-border dark:border-swiss-border-dark bg-white dark:bg-swiss-charcoal px-4 flex items-center justify-between select-none font-mono text-xs z-20">
      <!-- Left: Technical Identity -->
      <div class="flex items-center gap-3">
        <div class="w-5 h-5 bg-swiss-accent flex items-center justify-center text-white font-bold text-[11px] rounded-none">
          +
        </div>
        <div class="flex items-center gap-2">
          <span class="font-bold tracking-tight text-swiss-black dark:text-neutral-100 uppercase">
            AI-OCR SPRINT
          </span>
          <span class="text-swiss-muted text-[10px]">
            // RAG MULTIMODAL SUISSE
          </span>
        </div>
      </div>

      <!-- Center: Active Document Telemetry & Upload Trigger -->
      <div class="flex items-center gap-2">
        <div
          v-if="activeDoc"
          class="flex items-center gap-2 px-2.5 py-1 border border-swiss-border dark:border-swiss-border-dark bg-swiss-surface dark:bg-neutral-900 text-[11px]"
        >
          <span
            class="w-1.5 h-1.5 rounded-none"
            :class="activeDoc.status === 'ready' ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'"
          ></span>
          <span class="font-bold text-swiss-black dark:text-neutral-200 max-w-[180px] truncate">
            {{ activeDoc.filename }}
          </span>
          <span class="text-swiss-muted">
            ({{ activeDoc.page_count }} PÁGS)
          </span>
        </div>

        <button
          @click="showUploadModal = true"
          class="h-7 px-3 border border-swiss-border dark:border-swiss-border-dark hover:border-swiss-accent hover:text-swiss-accent transition-colors bg-white dark:bg-neutral-900 text-swiss-black dark:text-neutral-200 font-semibold tracking-wider uppercase text-[10px]"
        >
          [ + CARGAR PDF ]
        </button>
      </div>

      <!-- Right: Vision Gallery Trigger & Shortcuts -->
      <div class="flex items-center gap-2">
        <button
          @click="activeRightTab = 'search'"
          class="h-7 px-2.5 border border-swiss-border dark:border-swiss-border-dark hover:border-swiss-accent hover:text-swiss-accent transition-colors text-[10px] uppercase font-mono text-swiss-muted flex items-center gap-1.5"
          title="Abrir búsqueda de palabras clave"
        >
          <span>BUSCAR</span>
          <kbd class="px-1 py-0.2 border border-swiss-border dark:border-swiss-border-dark bg-swiss-surface dark:bg-neutral-800 text-[9px]">⌘K</kbd>
        </button>

        <button
          @click="showVisionModal = true"
          :disabled="!activeDoc || extractedImages.length === 0"
          class="h-7 px-3 border border-swiss-border dark:border-swiss-border-dark hover:border-swiss-accent hover:text-swiss-accent disabled:opacity-30 disabled:hover:border-swiss-border transition-colors text-[10px] uppercase font-mono font-bold flex items-center gap-1.5"
        >
          <span>FIGURAS</span>
          <span v-if="extractedImages.length > 0" class="text-swiss-accent">
            [{{ extractedImages.length }}]
          </span>
        </button>
      </div>
    </header>

    <!-- Main Workspace: Asymmetric Swiss Split-Screen Grid (55% / 45%) -->
    <main class="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-swiss-border dark:divide-swiss-border-dark">
      <!-- Left Panel (55%): PDF Viewer with Coordinate Overlay & Collapsible Figure Gallery -->
      <section class="lg:col-span-7 h-full overflow-hidden flex flex-col bg-neutral-100 dark:bg-neutral-950">
        <div class="flex-1 overflow-hidden relative flex flex-col">
          <PdfViewer
            ref="pdfViewerRef"
            :pdf-url="pdfUrl"
            :highlight-page="highlightPage"
            :highlight-bbox="highlightBbox"
          />
        </div>

        <!-- Collapsible Editorial Figure Gallery Drawer -->
        <FigureGallery
          v-if="activeDoc"
          :images="extractedImages"
          @jump-to-figure="handleJumpToFigure"
          @inspect-figure="handleInspectFigure"
        />
      </section>

      <!-- Right Panel (45%): Dual Tab Editorial Interaction (RAG Chat vs Keyword Search) -->
      <section class="lg:col-span-5 h-full overflow-hidden flex flex-col bg-white dark:bg-swiss-charcoal">
        <!-- Technical Tabs Header -->
        <div class="h-10 border-b border-swiss-border dark:border-swiss-border-dark flex items-center bg-swiss-surface dark:bg-neutral-900/60 font-mono text-[11px] select-none">
          <button
            @click="activeRightTab = 'chat'"
            class="flex-1 h-full border-r border-swiss-border dark:border-swiss-border-dark font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1.5"
            :class="activeRightTab === 'chat'
              ? 'bg-white dark:bg-swiss-charcoal text-swiss-accent border-b-2 border-b-swiss-accent'
              : 'text-swiss-muted hover:text-swiss-black dark:hover:text-white'"
          >
            [ 01 // ASISTENTE RAG ]
          </button>
          <button
            @click="activeRightTab = 'search'"
            class="flex-1 h-full font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-1.5"
            :class="activeRightTab === 'search'
              ? 'bg-white dark:bg-swiss-charcoal text-swiss-accent border-b-2 border-b-swiss-accent'
              : 'text-swiss-muted hover:text-swiss-black dark:hover:text-white'"
          >
            [ 02 // BÚSQUEDA LÉXICA ]
          </button>
        </div>

        <!-- Tab 1: Chat RAG Panel -->
        <div v-show="activeRightTab === 'chat'" class="flex-1 overflow-hidden">
          <ChatPanel
            :messages="chat.messages.value"
            :is-generating="chat.isGenerating.value"
            :disabled="!activeDoc || activeDoc.status !== 'ready'"
            @send="handleSendMessage"
            @clear="chat.clearChat"
            @citation-click="handleCitationClick"
          />
        </div>

        <!-- Tab 2: Keyword Search Panel -->
        <div v-show="activeRightTab === 'search'" class="flex-1 overflow-hidden">
          <KeywordSearch
            ref="keywordSearchRef"
            :document-id="activeDoc?.document_id || null"
            @jump-to-match="handleJumpToMatch"
          />
        </div>
      </section>
    </main>

    <!-- Upload Modal -->
    <div
      v-if="showUploadModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm select-none"
      @click.self="showUploadModal = false"
    >
      <div class="w-full max-w-lg bg-white dark:bg-swiss-charcoal border border-swiss-border dark:border-swiss-border-dark p-6 shadow-2xl space-y-4">
        <div class="flex items-center justify-between border-b border-swiss-border dark:border-swiss-border-dark pb-3">
          <h3 class="text-xs font-mono font-bold text-swiss-black dark:text-neutral-100 uppercase tracking-wider">
            [ INGESTA DE DOCUMENTO PDF ]
          </h3>
          <button @click="showUploadModal = false" class="text-swiss-muted hover:text-swiss-black dark:hover:text-white font-mono text-xs">
            ✕
          </button>
        </div>

        <DocumentUploader
          @upload-started="handleUploadStarted"
          @document-ready="handleDocumentReady"
        />
      </div>
    </div>

    <!-- Vision Inspector Modal -->
    <ImageInspectorModal
      :is-open="showVisionModal"
      :document-id="activeDoc?.document_id || null"
      :images="extractedImages"
      :initial-image-id="selectedInspectionImageId"
      @close="showVisionModal = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import type { Citation, DocumentDetailResponse, ExtractedImageMetadata } from './types';
import { ApiService } from './services/api';
import { useChat } from './composables/useChat';
import DocumentUploader from './components/DocumentUploader.vue';
import PdfViewer from './components/PdfViewer.vue';
import FigureGallery from './components/FigureGallery.vue';
import ChatPanel from './components/ChatPanel.vue';
import KeywordSearch from './components/KeywordSearch.vue';
import ImageInspectorModal from './components/ImageInspectorModal.vue';

const showUploadModal = ref(false);
const showVisionModal = ref(false);
const selectedInspectionImageId = ref<string | null>(null);
const activeRightTab = ref<'chat' | 'search'>('chat');

const activeDoc = ref<DocumentDetailResponse | null>(null);
const extractedImages = ref<ExtractedImageMetadata[]>([]);
const pdfUrl = ref<string | null>(null);

const highlightPage = ref<number | null>(null);
const highlightBbox = ref<number[] | null>(null);

const pdfViewerRef = ref<any>(null);
const keywordSearchRef = ref<any>(null);
const chat = useChat();

onMounted(async () => {
  window.addEventListener('keydown', handleGlobalKeyDown);
  try {
    const docs = await ApiService.listDocuments();
    if (docs.length > 0) {
      const readyDoc = docs.find((d) => d.status === 'ready') || docs[0];
      await selectDocument(readyDoc.document_id);
    } else {
      showUploadModal.value = true;
    }
  } catch {
    showUploadModal.value = true;
  }
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeyDown);
});

function handleGlobalKeyDown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    activeRightTab.value = 'search';
    keywordSearchRef.value?.focusInput();
  }
}

async function selectDocument(docId: string) {
  try {
    const doc = await ApiService.getDocument(docId);
    activeDoc.value = doc;
    pdfUrl.value = ApiService.getDocumentFileUrl(docId);

    const images = await ApiService.listDocumentImages(docId);
    extractedImages.value = images;
  } catch (err) {
    console.error('Failed to select document', err);
  }
}

function handleUploadStarted() {
  // Modal stays open to exhibit live SSE terminal stepper
}

async function handleDocumentReady(documentId: string) {
  showUploadModal.value = false;
  await selectDocument(documentId);
}

function handleSendMessage(query: string) {
  if (activeDoc.value) {
    chat.sendMessage(activeDoc.value.document_id, query, true); // true = streaming
  }
}

function handleCitationClick(citation: Citation) {
  highlightPage.value = citation.page_number;
  highlightBbox.value = citation.bbox || null;
  pdfViewerRef.value?.goToPage(citation.page_number, citation.bbox || null);
}

function handleJumpToMatch(payload: { pageNumber: number; bbox: number[] | null }) {
  highlightPage.value = payload.pageNumber;
  highlightBbox.value = payload.bbox;
  pdfViewerRef.value?.goToPage(payload.pageNumber, payload.bbox);
}

function handleJumpToFigure(payload: { pageNumber: number; bbox: number[] | null }) {
  highlightPage.value = payload.pageNumber;
  highlightBbox.value = payload.bbox;
  pdfViewerRef.value?.goToPage(payload.pageNumber, payload.bbox);
}

function handleInspectFigure(image: ExtractedImageMetadata) {
  selectedInspectionImageId.value = image.image_id;
  showVisionModal.value = true;
}
</script>
