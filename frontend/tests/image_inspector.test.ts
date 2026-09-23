import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import ImageInspectorModal from '../src/components/ImageInspectorModal.vue';
import { ApiService } from '../src/services/api';
import type { ExtractedImageMetadata, VisionQueryResponse } from '../src/types';

describe('ImageInspectorModal.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const sampleImage: ExtractedImageMetadata = {
    image_id: 'img_test_123',
    document_id: 'doc-swiss-1',
    page_number: 4,
    bbox: [50.0, 120.0, 450.0, 380.0],
    width: 800,
    height: 600,
    file_path: '/path/to/img.png',
    url: '/api/v1/documents/doc-swiss-1/images/img_test_123',
    order: 3,
    caption: 'Figura 4.1: Distribución empírica de latencias',
    section_title: 'Sección 4: Análisis Experimental',
    surrounding_text: 'Sección: Análisis Experimental // Pie de figura: Distribución empírica // Párrafo anterior: Los benchmarks demuestran baja latencia.',
  };

  it('renders technical header, metadata tags, and image-to-text context block', () => {
    const wrapper = mount(ImageInspectorModal, {
      props: {
        isOpen: true,
        documentId: 'doc-swiss-1',
        images: [sampleImage],
      },
    });

    expect(wrapper.text()).toContain('[ 04 // INSPECCIÓN VISUAL MULTIMODAL · MOONDREAM ]');
    expect(wrapper.text()).toContain('[ REF. PÁG: ]');
    expect(wrapper.text()).toContain('PÁGINA 4');
    expect(wrapper.text()).toContain('[ BBOX COORDS: ]');
    expect(wrapper.text()).toContain('50, 120, 450, 380');

    // Context card
    expect(wrapper.text()).toContain('[ CONTEXTO TEXTUAL ADYACENTE // PÁG. 4 ]');
    expect(wrapper.text()).toContain('Sección 4: Análisis Experimental');
    expect(wrapper.text()).toContain('Figura 4.1: Distribución empírica de latencias');
    expect(wrapper.text()).toContain('Los benchmarks demuestran baja latencia');
  });

  it('triggers ApiService.queryVision with prompt and renders numerical estimation warning alert', async () => {
    const mockResponse: VisionQueryResponse = {
      image_id: 'img_test_123',
      analysis: 'La figura muestra que el 85% de las solicitudes se completan en menos de 1.2 segundos.',
      has_numerical_estimates: true,
      estimation_warning: 'Aviso: Esta respuesta contiene valores numéricos interpretados visualmente.',
      metrics: { vision_time: 0.85, total_time: 0.92 },
    };

    const visionSpy = vi.spyOn(ApiService, 'queryVision').mockResolvedValue(mockResponse);

    const wrapper = mount(ImageInspectorModal, {
      props: {
        isOpen: true,
        documentId: 'doc-swiss-1',
        images: [sampleImage],
      },
    });

    const input = wrapper.find('input[type="text"]');
    await input.setValue('¿Cuál es la tasa de solicitudes?');

    const analyzeBtn = wrapper.findAll('button').find((b) => b.text().includes('ANALIZAR'));
    expect(analyzeBtn).toBeDefined();
    await analyzeBtn!.trigger('click');

    expect(visionSpy).toHaveBeenCalledWith('doc-swiss-1', 'img_test_123', '¿Cuál es la tasa de solicitudes?');

    // Wait for promise tick
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(wrapper.text()).toContain('La figura muestra que el 85% de las solicitudes');
    expect(wrapper.text()).toContain('[ ESTIMACIÓN VISUAL NO DETERMINISTA ]');
    expect(wrapper.text()).toContain('Aviso: Esta respuesta contiene valores numéricos interpretados visualmente.');
    expect(wrapper.text()).toContain('INFERENCIA VISUAL: 850ms');
    expect(wrapper.text()).toContain('TOTAL: 920ms');
  });

  it('emits close event when clicking CERRAR', async () => {
    const wrapper = mount(ImageInspectorModal, {
      props: {
        isOpen: true,
        documentId: 'doc-swiss-1',
        images: [sampleImage],
      },
    });

    const closeBtn = wrapper.findAll('button').find((b) => b.text().includes('CERRAR'));
    expect(closeBtn).toBeDefined();
    await closeBtn!.trigger('click');

    expect(wrapper.emitted('close')).toBeTruthy();
  });
});
