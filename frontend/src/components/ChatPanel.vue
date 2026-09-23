<template>
  <div class="h-full flex flex-col bg-white dark:bg-swiss-charcoal border-l border-swiss-border dark:border-swiss-border-dark select-none">
    <!-- Technical Module Header -->
    <div class="h-12 border-b border-swiss-border dark:border-swiss-border-dark px-4 flex items-center justify-between bg-swiss-surface dark:bg-neutral-900/60">
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 bg-emerald-500 rounded-none inline-block"></span>
        <span class="text-[11px] font-mono font-semibold tracking-wider text-swiss-black dark:text-neutral-200 uppercase">
          [ 03 // ASISTENTE RAG MULTIMODAL ]
        </span>
      </div>
      <button
        v-if="messages.length > 0"
        @click="$emit('clear')"
        class="text-[11px] font-mono text-swiss-muted hover:text-swiss-black dark:hover:text-white uppercase transition-colors"
        title="Limpiar Conversación"
      >
        [ LIMPIAR ]
      </button>
    </div>

    <!-- Message Stream -->
    <div ref="chatContainerRef" class="flex-1 overflow-y-auto p-4 space-y-6">
      <!-- Empty State -->
      <div
        v-if="messages.length === 0"
        class="h-full flex flex-col items-center justify-center text-center p-8 text-swiss-muted font-mono"
      >
        <div class="w-8 h-8 border border-swiss-border dark:border-swiss-border-dark flex items-center justify-center text-xs mb-3 text-swiss-black dark:text-white">
          ¶
        </div>
        <p class="text-xs font-semibold uppercase tracking-wider text-swiss-black dark:text-neutral-300">
          Consulta Documental Rigurosa
        </p>
        <p class="text-[11px] mt-1 max-w-[260px] leading-relaxed">
          Las respuestas se fundamentan matemáticamente en los fragmentos recuperados con citaciones verificables.
        </p>
      </div>

      <!-- Messages Loop -->
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="space-y-1.5"
      >
        <!-- Role Identifier Tag -->
        <div class="flex items-center justify-between text-[10px] font-mono">
          <span
            class="px-1.5 py-0.5 border rounded-none font-bold uppercase tracking-wider"
            :class="msg.role === 'user'
              ? 'border-swiss-black dark:border-neutral-400 text-swiss-black dark:text-neutral-200 bg-neutral-100 dark:bg-neutral-800'
              : 'border-swiss-accent text-swiss-accent bg-swiss-accent/5'"
          >
            [ {{ msg.role === 'user' ? 'USUARIO' : 'ASISTENTE // RAG' }} ]
          </span>
          <span class="text-swiss-muted">{{ msg.timestamp }}</span>
        </div>

        <!-- Content Block -->
        <div
          class="border border-swiss-border dark:border-swiss-border-dark p-4 rounded-none text-xs leading-relaxed"
          :class="msg.role === 'user'
            ? 'bg-swiss-surface dark:bg-neutral-900/50 text-swiss-black dark:text-neutral-200 font-sans'
            : 'bg-white dark:bg-swiss-charcoal text-swiss-black dark:text-neutral-100'"
        >
          <!-- Markdown / Text Stream -->
          <div
            class="prose prose-sm dark:prose-invert max-w-none break-words font-sans selection:bg-swiss-accent selection:text-white"
            v-html="renderMarkdown(msg.content)"
          ></div>

          <!-- Verifiable Citation Badges -->
          <div v-if="msg.citations && msg.citations.length > 0" class="mt-3 pt-3 border-t border-swiss-border dark:border-swiss-border-dark">
            <span class="text-[10px] font-mono font-bold text-swiss-muted uppercase tracking-wider block mb-1.5">
              [ FUENTES CITADAS ]
            </span>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="(cit, idx) in msg.citations"
                :key="idx"
                @click="$emit('citation-click', cit)"
                class="group inline-flex items-center gap-1.5 text-[11px] font-mono px-2 py-1 border border-swiss-border dark:border-swiss-border-dark bg-swiss-surface dark:bg-neutral-900 hover:border-swiss-accent hover:text-swiss-accent transition-colors"
                :title="cit.snippet"
              >
                <span class="text-swiss-accent font-bold">Pág. {{ cit.page_number }}</span>
                <span class="text-swiss-muted text-[10px] truncate max-w-[120px]">
                  #{{ cit.chunk_id }}
                </span>
              </button>
            </div>
          </div>

          <!-- Latency & Telemetry Footer -->
          <div v-if="msg.metrics && Object.keys(msg.metrics).length > 0" class="flex flex-wrap items-center gap-3 mt-3 pt-2 border-t border-swiss-border dark:border-swiss-border-dark text-[10px] font-mono text-swiss-muted">
            <span v-if="msg.metrics.retrieval_time">
              Recuperación: {{ Math.round(msg.metrics.retrieval_time * 1000) }}ms
            </span>
            <span v-if="msg.metrics.ttft">
              TTFT: {{ Number(msg.metrics.ttft).toFixed(2) }}s
            </span>
            <span v-if="msg.metrics.total_time" class="text-swiss-black dark:text-neutral-200 font-bold">
              TOTAL: {{ Number(msg.metrics.total_time).toFixed(2) }}s
            </span>
            <span v-if="msg.metrics.tokens_per_sec" class="text-swiss-accent font-bold">
              {{ msg.metrics.tokens_per_sec }} TOK/S
            </span>
          </div>
        </div>
      </div>

      <!-- Generating Live Pulse Indicator -->
      <div v-if="isGenerating" class="flex items-center gap-2 text-swiss-muted text-xs font-mono py-1">
        <span class="inline-block w-2 h-2 bg-swiss-accent animate-ping"></span>
        <span class="tracking-wider uppercase text-[10px]">
          [ TRANSMITIENDO RESPUESTA // QWEN 2.5 ]
        </span>
      </div>
    </div>

    <!-- Input Form -->
    <div class="p-3 border-t border-swiss-border dark:border-swiss-border-dark bg-swiss-surface dark:bg-neutral-900/60">
      <form @submit.prevent="handleSubmit" class="flex gap-2">
        <input
          v-model="inputQuery"
          type="text"
          placeholder="Formula una consulta analítica sobre el documento..."
          :disabled="isGenerating || disabled"
          class="flex-1 h-9 px-3 text-xs font-sans bg-white dark:bg-swiss-charcoal border border-swiss-border dark:border-swiss-border-dark rounded-none text-swiss-black dark:text-neutral-100 placeholder:text-swiss-muted focus:outline-none focus:border-swiss-accent focus:ring-1 focus:ring-swiss-accent disabled:opacity-40"
        />
        <button
          type="submit"
          :disabled="!inputQuery.trim() || isGenerating || disabled"
          class="px-4 h-9 bg-swiss-accent hover:bg-blue-700 disabled:bg-neutral-300 dark:disabled:bg-neutral-800 disabled:text-neutral-500 text-white rounded-none text-xs font-mono font-bold tracking-wider uppercase transition-colors flex items-center justify-center"
        >
          ENVIAR
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue';
import { marked } from 'marked';
import type { ChatMessage, Citation } from '../types';

const props = defineProps<{
  messages: ChatMessage[];
  isGenerating: boolean;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: 'send', query: string): void;
  (e: 'clear'): void;
  (e: 'citation-click', citation: Citation): void;
}>();

const inputQuery = ref('');
const chatContainerRef = ref<HTMLDivElement | null>(null);

function renderMarkdown(content: string): string {
  try {
    return marked.parse(content, { async: false }) as string;
  } catch {
    return content;
  }
}

function handleSubmit() {
  if (inputQuery.value.trim() && !props.isGenerating) {
    emit('send', inputQuery.value.trim());
    inputQuery.value = '';
    scrollToBottom();
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight;
    }
  });
}

watch(
  () => props.messages.length,
  () => scrollToBottom()
);

watch(
  () => props.messages[props.messages.length - 1]?.content,
  () => scrollToBottom()
);
</script>
