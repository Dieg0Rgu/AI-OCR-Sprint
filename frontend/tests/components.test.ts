import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import SSEProgressBar from '../src/components/SSEProgressBar.vue';
import ChatPanel from '../src/components/ChatPanel.vue';
import type { Citation } from '../src/types';

describe('SSEProgressBar.vue', () => {
  it('renders extracting state and progress percentage correctly', () => {
    const wrapper = mount(SSEProgressBar, {
      props: {
        status: 'extracting',
        progress: 35,
        message: 'Extrayendo texto estructurado...',
        latencies: { extraction_time: 0.42 },
      },
    });

    expect(wrapper.text()).toContain('2. Extracción PyMuPDF');
    expect(wrapper.text()).toContain('35%');
    expect(wrapper.text()).toContain('Extrayendo texto estructurado...');
    expect(wrapper.text()).toContain('Extracción: 0.42s');
  });

  it('renders ready state with 100% progress', () => {
    const wrapper = mount(SSEProgressBar, {
      props: {
        status: 'ready',
        progress: 100,
        message: 'Listo para consultas',
        latencies: { total_ingestion_time: 1.25 },
      },
    });

    expect(wrapper.text()).toContain('✓ Listo para Consultas');
    expect(wrapper.text()).toContain('100%');
    expect(wrapper.text()).toContain('Total: 1.25s');
  });
});

describe('ChatPanel.vue', () => {
  it('renders citations and emits citation-click on click', async () => {
    const sampleCitation: Citation = {
      page_number: 15,
      chunk_id: 'doc_p15_c0',
      snippet: 'El algoritmo RRF fusiona rankings densos y léxicos con k=60',
    };

    const wrapper = mount(ChatPanel, {
      props: {
        messages: [
          {
            id: '1',
            role: 'assistant',
            content: 'Respuesta analítica basada en el documento.',
            citations: [sampleCitation],
            metrics: { retrieval_time: 0.045, llm_time: 0.85, total_time: 0.895 },
            timestamp: '12:00:00',
          },
        ],
        isGenerating: false,
      },
    });

    expect(wrapper.text()).toContain('Pág. 15');
    expect(wrapper.text()).toContain('#doc_p15_c0');
    expect(wrapper.text()).toContain('Recuperación: 45ms');

    // Click on citation badge
    const citButton = wrapper.find('button[title*="El algoritmo RRF"]');
    expect(citButton.exists()).toBe(true);

    await citButton.trigger('click');
    expect(wrapper.emitted('citation-click')).toBeTruthy();
    expect(wrapper.emitted('citation-click')![0][0]).toEqual(sampleCitation);
  });
});
