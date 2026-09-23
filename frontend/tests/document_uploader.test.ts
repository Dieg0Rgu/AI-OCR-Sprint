import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import DocumentUploader from '../src/components/DocumentUploader.vue';
import { ApiService } from '../src/services/api';

describe('DocumentUploader.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders technical Swiss header with format specifications', () => {
    const wrapper = mount(DocumentUploader);
    expect(wrapper.text()).toContain('[ 01 // INGESTA DE DOCUMENTO ]');
    expect(wrapper.text()).toContain('FORMATO: PDF / MAX 50 MB');
  });

  it('displays diagnostic error card when non-PDF file is supplied', async () => {
    const wrapper = mount(DocumentUploader);

    // Call processFile indirectly via drop or directly by passing an invalid File
    const invalidFile = new File(['hello world'], 'notes.txt', { type: 'text/plain' });

    // Spy on validatePdfPreflight
    vi.spyOn(ApiService, 'validatePdfPreflight').mockResolvedValue({
      valid: false,
      errorCode: 'ERROR_INVALID_EXTENSION',
      message: 'El archivo seleccionado no tiene extensión .pdf válida.',
    });

    // Simulate drop
    const dropzone = wrapper.find('.cursor-pointer');
    await dropzone.trigger('drop', {
      dataTransfer: {
        files: [invalidFile],
      },
    });

    // Wait for async validation to settle
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(wrapper.text()).toContain('[ ERROR_INVALID_EXTENSION ]');
    expect(wrapper.text()).toContain('El archivo seleccionado no tiene extensión .pdf válida.');
    expect(wrapper.text()).toContain('REINTENTAR INGESTA');
  });

  it('displays diagnostic error card when magic bytes validation fails', async () => {
    const wrapper = mount(DocumentUploader);

    const corruptPdf = new File(['NOT_A_REAL_PDF_HEADER'], 'corrupt.pdf', { type: 'application/pdf' });

    vi.spyOn(ApiService, 'validatePdfPreflight').mockResolvedValue({
      valid: false,
      errorCode: 'ERROR_INVALID_MIME_OR_MAGIC',
      message: 'Cabecera de archivo corrupta o inválida (se esperaba %PDF-).',
    });

    const dropzone = wrapper.find('.cursor-pointer');
    await dropzone.trigger('drop', {
      dataTransfer: {
        files: [corruptPdf],
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(wrapper.text()).toContain('[ ERROR_INVALID_MIME_OR_MAGIC ]');
    expect(wrapper.text()).toContain('Cabecera de archivo corrupta o inválida');
  });

  it('proceeds with upload and emits upload-started on valid PDF file', async () => {
    vi.spyOn(ApiService, 'validatePdfPreflight').mockResolvedValue({ valid: true });
    const uploadSpy = vi.spyOn(ApiService, 'uploadDocument').mockResolvedValue({
      document_id: 'doc-swiss-99',
      filename: 'sample_document.pdf',
      status: 'uploaded',
      message: 'Subida exitosa',
    });

    const wrapper = mount(DocumentUploader);

    const validPdf = new File(['%PDF-1.4 sample content'], 'sample_document.pdf', { type: 'application/pdf' });

    const dropzone = wrapper.find('.cursor-pointer');
    await dropzone.trigger('drop', {
      dataTransfer: {
        files: [validPdf],
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(uploadSpy).toHaveBeenCalledWith(validPdf);
    expect(wrapper.emitted('upload-started')).toBeTruthy();
    expect(wrapper.emitted('upload-started')![0][0]).toBe('doc-swiss-99');
  });
});
