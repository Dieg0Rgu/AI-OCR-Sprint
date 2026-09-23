import { ref } from 'vue';

export function usePdfViewer() {
  const currentPage = ref<number>(1);
  const totalPages = ref<number>(1);
  const zoomLevel = ref<number>(1.0);
  const activeBbox = ref<number[] | null>(null);
  const pdfUrl = ref<string | null>(null);
  const isLoading = ref<boolean>(false);

  function loadPdf(url: string, initialPage = 1) {
    pdfUrl.value = url;
    currentPage.value = initialPage;
    activeBbox.value = null;
  }

  function goToPage(page: number, bbox: number[] | null = null) {
    if (page >= 1 && page <= totalPages.value) {
      currentPage.value = page;
      activeBbox.value = bbox;
    }
  }

  function nextPage() {
    if (currentPage.value < totalPages.value) {
      currentPage.value++;
      activeBbox.value = null;
    }
  }

  function prevPage() {
    if (currentPage.value > 1) {
      currentPage.value--;
      activeBbox.value = null;
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

  return {
    currentPage,
    totalPages,
    zoomLevel,
    activeBbox,
    pdfUrl,
    isLoading,
    loadPdf,
    goToPage,
    nextPage,
    prevPage,
    zoomIn,
    zoomOut,
    resetZoom,
  };
}
