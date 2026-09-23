export type DocumentStatus =
  | 'uploaded'
  | 'extracting'
  | 'ocr_processing'
  | 'chunking'
  | 'indexing'
  | 'ready'
  | 'failed';

export interface ChunkMetadata {
  chunk_id: string;
  document_id: string;
  page_number: number;
  bbox: number[] | null;
  associated_image_ids: string[];
}

export interface ExtractedImageMetadata {
  image_id: string;
  document_id: string;
  page_number: number;
  bbox: number[] | null;
  width: number;
  height: number;
  file_path: string;
  url: string;
  order?: number;
  caption?: string | null;
  section_title?: string | null;
  surrounding_text?: string | null;
}

export interface DocumentDetailResponse {
  document_id: string;
  filename: string;
  file_size_bytes: number;
  status: DocumentStatus;
  page_count: number;
  total_chunks: number;
  total_images: number;
  stage_latencies: Record<string, number>;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  status: DocumentStatus;
  message: string;
}

export interface UploadErrorDetail {
  error_code: string;
  detail: string;
}

export interface SSEEventPayload {
  document_id: string;
  status: DocumentStatus;
  progress_percent: number;
  message: string;
  error?: string | null;
  stage_latencies?: Record<string, number>;
  timestamp: number;
}

export interface Citation {
  page_number: number;
  chunk_id: string;
  snippet: string;
  bbox?: number[] | null;
}

export interface RAGResponse {
  answer: string;
  citations: Citation[];
  metrics: Record<string, number>;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  metrics?: {
    retrieval_time?: number;
    llm_time?: number;
    ttft?: number;
    total_time?: number;
    tokens_per_sec?: number;
    token_count?: number;
    [key: string]: number | undefined;
  };
  timestamp: string;
}

export interface KeywordSearchMatch {
  match_id: string;
  document_id: string;
  page_number: number;
  chunk_id: string;
  matched_text: string;
  snippet: string;
  bbox: number[] | null;
  line_number?: number | null;
}

export interface KeywordSearchResponse {
  document_id: string;
  query: string;
  case_sensitive: boolean;
  exact_match: boolean;
  total_matches: number;
  matches: KeywordSearchMatch[];
}

export interface VisionQueryRequest {
  document_id: string;
  image_id: string;
  prompt: string;
}

export interface VisionQueryResponse {
  image_id: string;
  analysis: string;
  has_numerical_estimates: boolean;
  estimation_warning?: string | null;
  metrics: Record<string, number>;
}
