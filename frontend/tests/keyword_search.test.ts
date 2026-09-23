import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import KeywordSearch from '../src/components/KeywordSearch.vue';
import { ApiService } from '../src/services/api';
import type { KeywordSearchResponse } from '../src/types';

describe('KeywordSearch.vue', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  const mockResponse: KeywordSearchResponse = {
    document_id: 'doc-123',
    query: 'atención',
    total_matches: 2,
    case_sensitive: false,
    exact_match: false,
    matches: [
      {
        match_id: 'match-p1-0',
        document_id: 'doc-123',
        chunk_id: 'chunk-p1-0',
        matched_text: 'atención',
        page_number: 1,
        line_number: 5,
        snippet: 'Mecanismo de **atención** auto-referencial...',
        bbox: [100, 200, 300, 50],
      },
      {
        match_id: 'match-p3-0',
        document_id: 'doc-123',
        chunk_id: 'chunk-p3-0',
        matched_text: 'atención',
        page_number: 3,
        line_number: 12,
        snippet: 'Cálculo de matrices de **atención** multi-cabeza...',
        bbox: [120, 220, 280, 45],
      },
    ],
  };

  it('renders technical header with keyboard shortcut hint', () => {
    const wrapper = mount(KeywordSearch, {
      props: { documentId: 'doc-123' },
    });

    expect(wrapper.text()).toContain('[ 02 // BÚSQUEDA LÉXICA ]');
    expect(wrapper.text()).toContain('⌘K');
    expect(wrapper.text()).toContain('Ctrl+K');
  });

  it('renders initial empty state when no search query is typed', () => {
    const wrapper = mount(KeywordSearch, {
      props: { documentId: 'doc-123' },
    });

    expect(wrapper.text()).toContain('Índice Analítico Léxico');
    expect(wrapper.text()).toContain('Escribe para indexar ocurrencias');
  });

  it('triggers search with debounce and emits jump-to-match on first match', async () => {
    const searchSpy = vi.spyOn(ApiService, 'searchDocumentKeywords').mockResolvedValue(mockResponse);

    const wrapper = mount(KeywordSearch, {
      props: { documentId: 'doc-123' },
    });

    const input = wrapper.find('input[type="text"]');
    await input.setValue('atención');

    // Before debounce timer fires
    expect(searchSpy).not.toHaveBeenCalled();

    // Advance debounce timer
    await vi.advanceTimersByTimeAsync(300);

    expect(searchSpy).toHaveBeenCalledWith('doc-123', 'atención', false, false);

    // Verify counter subheader
    expect(wrapper.text()).toContain('[ COINCIDENCIA 1 DE 2');
    expect(wrapper.text()).toContain('EN PÁG. 1');

    // Emits jump-to-match for the first match
    expect(wrapper.emitted('jump-to-match')).toBeTruthy();
    expect(wrapper.emitted('jump-to-match')![0][0]).toEqual({
      pageNumber: 1,
      bbox: [100, 200, 300, 50],
    });
  });

  it('toggles case-sensitive and exact-match filters', async () => {
    const searchSpy = vi.spyOn(ApiService, 'searchDocumentKeywords').mockResolvedValue(mockResponse);

    const wrapper = mount(KeywordSearch, {
      props: { documentId: 'doc-123' },
    });

    const input = wrapper.find('input[type="text"]');
    await input.setValue('atención');
    await vi.advanceTimersByTimeAsync(300);

    // Toggle Aa (case sensitive)
    const caseBtn = wrapper.findAll('button').find((b) => b.text() === 'Aa');
    expect(caseBtn).toBeDefined();
    await caseBtn!.trigger('click');
    await vi.advanceTimersByTimeAsync(300);

    expect(searchSpy).toHaveBeenLastCalledWith('doc-123', 'atención', true, false);

    // Toggle " " (exact match)
    const exactBtn = wrapper.findAll('button').find((b) => b.text() === '" "');
    expect(exactBtn).toBeDefined();
    await exactBtn!.trigger('click');
    await vi.advanceTimersByTimeAsync(300);

    expect(searchSpy).toHaveBeenLastCalledWith('doc-123', 'atención', true, true);
  });

  it('navigates through matches with stepper buttons and wraps around', async () => {
    vi.spyOn(ApiService, 'searchDocumentKeywords').mockResolvedValue(mockResponse);

    const wrapper = mount(KeywordSearch, {
      props: { documentId: 'doc-123' },
    });

    const input = wrapper.find('input[type="text"]');
    await input.setValue('atención');
    await vi.advanceTimersByTimeAsync(300);

    const nextBtn = wrapper.findAll('button').find((b) => b.attributes('title') === 'Siguiente coincidencia');
    const prevBtn = wrapper.findAll('button').find((b) => b.attributes('title') === 'Coincidencia anterior');
    expect(nextBtn).toBeDefined();
    expect(prevBtn).toBeDefined();

    // Next match -> index 1 (page 3)
    await nextBtn!.trigger('click');
    expect(wrapper.text()).toContain('[ COINCIDENCIA 2 DE 2');
    expect(wrapper.text()).toContain('EN PÁG. 3');

    // Next match again -> wraps around to index 0 (page 1)
    await nextBtn!.trigger('click');
    expect(wrapper.text()).toContain('[ COINCIDENCIA 1 DE 2');
    expect(wrapper.text()).toContain('EN PÁG. 1');

    // Prev match -> wraps backwards to index 1 (page 3)
    await prevBtn!.trigger('click');
    expect(wrapper.text()).toContain('[ COINCIDENCIA 2 DE 2');
    expect(wrapper.text()).toContain('EN PÁG. 3');
  });

  it('clicking a match row selects it and emits jump-to-match', async () => {
    vi.spyOn(ApiService, 'searchDocumentKeywords').mockResolvedValue(mockResponse);

    const wrapper = mount(KeywordSearch, {
      props: { documentId: 'doc-123' },
    });

    const input = wrapper.find('input[type="text"]');
    await input.setValue('atención');
    await vi.advanceTimersByTimeAsync(300);

    const rows = wrapper.findAll('.cursor-pointer');
    expect(rows.length).toBe(2);

    await rows[1].trigger('click');
    expect(wrapper.text()).toContain('[ COINCIDENCIA 2 DE 2');
    const emitted = wrapper.emitted('jump-to-match')!;
    expect(emitted[emitted.length - 1][0]).toEqual({
      pageNumber: 3,
      bbox: [120, 220, 280, 45],
    });
  });

  it('renders no results message when query returns 0 matches', async () => {
    vi.spyOn(ApiService, 'searchDocumentKeywords').mockResolvedValue({
      document_id: 'doc-123',
      query: 'inexistente',
      total_matches: 0,
      case_sensitive: false,
      exact_match: false,
      matches: [],
    });

    const wrapper = mount(KeywordSearch, {
      props: { documentId: 'doc-123' },
    });

    const input = wrapper.find('input[type="text"]');
    await input.setValue('inexistente');
    await vi.advanceTimersByTimeAsync(300);

    expect(wrapper.text()).toContain('0 coincidencias encontradas');
    expect(wrapper.text()).toContain('No se encontraron coincidencias para "inexistente"');
  });
});
