import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import FigureGallery from '../src/components/FigureGallery.vue';
import type { ExtractedImageMetadata } from '../src/types';

describe('FigureGallery.vue', () => {
  const sampleImages: ExtractedImageMetadata[] = [
    {
      image_id: 'img_doc_1_0_abc123',
      document_id: 'doc-123',
      page_number: 1,
      bbox: [50, 100, 200, 150],
      width: 400,
      height: 300,
      file_path: '/path/to/img1.png',
      url: '/api/v1/documents/doc-123/images/img_doc_1_0_abc123',
      order: 1,
      caption: 'Figura 1.1: Esquema de arquitectura modular',
      section_title: 'Sección 1: Introducción',
      surrounding_text: 'Contexto textual de la arquitectura del sistema.',
    },
    {
      image_id: 'img_doc_5_0_def456',
      document_id: 'doc-123',
      page_number: 5,
      bbox: [60, 200, 300, 250],
      width: 600,
      height: 450,
      file_path: '/path/to/img2.png',
      url: '/api/v1/documents/doc-123/images/img_doc_5_0_def456',
      order: 2,
      caption: 'Gráfico 5.2: Tiempos de latencia y Throughput',
      section_title: 'Sección 5: Métricas de Evaluación',
      surrounding_text: 'Resultados experimentales de la evaluación de latencia.',
    },
  ];

  it('renders technical Swiss header with total figures count', () => {
    const wrapper = mount(FigureGallery, {
      props: { images: sampleImages },
    });

    expect(wrapper.text()).toContain('[ 01 // GALERÍA DE FIGURAS INDEXADAS ]');
    expect(wrapper.text()).toContain('[2 / 2]');
  });

  it('renders figure cards with metadata and action buttons', () => {
    const wrapper = mount(FigureGallery, {
      props: { images: sampleImages },
    });

    expect(wrapper.text()).toContain('#IMG_01');
    expect(wrapper.text()).toContain('[ PÁG. 01 ]');
    expect(wrapper.text()).toContain('Figura 1.1: Esquema de arquitectura modular');

    expect(wrapper.text()).toContain('#IMG_02');
    expect(wrapper.text()).toContain('[ PÁG. 05 ]');
    expect(wrapper.text()).toContain('Gráfico 5.2: Tiempos de latencia y Throughput');
  });

  it('filters figures by search query in caption or page number', async () => {
    const wrapper = mount(FigureGallery, {
      props: { images: sampleImages },
    });

    const searchInput = wrapper.find('input[type="text"]');
    await searchInput.setValue('latencia');

    expect(wrapper.text()).toContain('Gráfico 5.2: Tiempos de latencia');
    expect(wrapper.text()).not.toContain('Esquema de arquitectura');
    expect(wrapper.text()).toContain('[1 / 2]');

    // Filter by page number
    await searchInput.setValue('1');
    expect(wrapper.text()).toContain('Figura 1.1');
    expect(wrapper.text()).not.toContain('Gráfico 5.2');
  });

  it('emits jump-to-figure event when clicking IR A PÁG', async () => {
    const wrapper = mount(FigureGallery, {
      props: { images: sampleImages },
    });

    const jumpButtons = wrapper.findAll('button').filter((b) => b.text().includes('IR A PÁG'));
    expect(jumpButtons.length).toBe(2);

    await jumpButtons[0].trigger('click');

    expect(wrapper.emitted('jump-to-figure')).toBeTruthy();
    expect(wrapper.emitted('jump-to-figure')![0][0]).toEqual({
      pageNumber: 1,
      bbox: [50, 100, 200, 150],
    });
  });

  it('emits inspect-figure event when clicking MOONDREAM button or thumbnail', async () => {
    const wrapper = mount(FigureGallery, {
      props: { images: sampleImages },
    });

    const moondreamButtons = wrapper.findAll('button').filter((b) => b.text() === 'MOONDREAM');
    expect(moondreamButtons.length).toBe(2);

    await moondreamButtons[1].trigger('click');

    expect(wrapper.emitted('inspect-figure')).toBeTruthy();
    expect(wrapper.emitted('inspect-figure')![0][0]).toEqual(sampleImages[1]);
  });

  it('toggles collapse and expand when clicking header bar', async () => {
    const wrapper = mount(FigureGallery, {
      props: { images: sampleImages },
    });

    const header = wrapper.find('.cursor-pointer');
    expect(wrapper.text()).toContain('▼ OCULTAR');

    // Click to collapse
    await header.trigger('click');
    expect(wrapper.text()).toContain('▲ MOSTRAR');
    expect(wrapper.find('input[type="text"]').exists()).toBe(false);

    // Click to expand again
    await header.trigger('click');
    expect(wrapper.text()).toContain('▼ OCULTAR');
    expect(wrapper.find('input[type="text"]').exists()).toBe(true);
  });
});
