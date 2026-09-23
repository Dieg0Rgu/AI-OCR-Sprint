# AI-OCR Sprint: Sistema de RAG Multimodal sobre Documentos PDF Complejos

Sistema de grado productivo para procesamiento asíncrono, indexación híbrida y consulta conversacional multimodal sobre documentos PDF complejos (de 20 a cientos de páginas). Diseñado con arquitectura desacoplada mediante interfaces, búsqueda híbrida con Reciprocal Rank Fusion (RRF), citaciones verificables e inspección visual con LLaVA 7B.

---

## 🏛️ Arquitectura del Sistema

```
                         ┌──────────────────────────────────────────────┐
                         │              Frontend (Vue 3)                │
                         │   PdfViewer ─ ChatPanel ─ ImageInspector     │
                         └──────────────────────┬───────────────────────┘
                                                │ SSE Stream / REST
                                                ▼
                         ┌──────────────────────────────────────────────┐
                         │              Backend (FastAPI)               │
                         │      Asynchronous Ingestion Pipeline         │
                         └──────┬───────────────┬────────────────┬──────┘
                                │               │                │
            ┌───────────────────▼──┐     ┌──────▼────────┐   ┌───▼──────────────┐
            │ PyMuPDF (fitz) + OCR │     │ Qdrant Vector │   │ Ollama Inferencia│
            │ Extract Text, BBoxes │     │ Densa + BM25  │   │ Qwen 2.5 (Text)  │
            │ & Figures (PNG/JPEG) │     │ Híbrido (RRF) │   │ LLaVA 7B (Vision)│
            └──────────────────────┘     └───────────────┘   └──────────────────┘
```

### Características Principales

1. **Pipeline Asíncrono no bloqueante:**
   - La carga (`POST /api/v1/documents/upload`) responde inmediatamente con `202 Accepted` y `document_id`.
   - La máquina de estados (`uploaded` ➔ `extracting` ➔ `ocr_processing` ➔ `chunking` ➔ `indexing` ➔ `ready` | `failed`) emite eventos en tiempo real mediante **Server-Sent Events (SSE)** en `/api/v1/documents/{id}/events`.
2. **Procesamiento de PDF y Multimodal:**
   - Extracción de texto estructurado y coordenadas `bbox` con **PyMuPDF (`pymupdf`)**.
   - Extracción automática de figuras e imágenes embebidas con metadatos de página (`image_id`, `page_number`, `bbox`, `width`, `height`).
   - **OCR Fallback** automático con Tesseract para páginas escaneadas o regiones sin texto vectorial nativo.
3. **Búsqueda Híbrida y Fusión RRF:**
   - Combina búsqueda densa en **Qdrant** (embeddings vectoriales) y búsqueda léxica **BM25** (Okapi BM25).
   - Fusión mediante **Reciprocal Rank Fusion (RRF)**:
     $$RRF\_score(d) = \sum_{m \in M} \frac{1}{60 + r_m(d)}$$
4. **Citas Verificables y Anti-Alucinación:**
   - Generación de respuestas con **Qwen 2.5** basada estrictamente en los fragmentos de contexto.
   - Cada afirmación incluye citas con `page_number`, `chunk_id` y `snippet`.
   - Al hacer clic en una cita desde la interfaz, el visor de PDF navega instantáneamente a la página citada y la resalta.
5. **Inspección Visual de Figuras con LLaVA 7B:**
   - Galería interactiva para consultar gráficos, esquemas y diagramas extraídos.
   - **Detector de Estimación Numérica:** Identifica automáticamente si una respuesta sobre un gráfico contiene inferencias cuantitativas visuales y añade una advertencia destacada para prevenir alucinaciones numéricas.

---

## 🚀 Inicio Rápido con Docker Compose

La forma recomendada de desplegar la suite completa (`backend`, `frontend`, `qdrant`, `ollama`):

```bash
# 1. Clonar el repositorio y copiar variables de entorno
cp .env.example .env

# 2. Iniciar todos los servicios
docker compose up --build -d

# 3. Descargar modelos en el contenedor de Ollama
docker exec -it pdf_rag_ollama ollama pull qwen2.5:7b
docker exec -it pdf_rag_ollama ollama pull llava:7b
docker exec -it pdf_rag_ollama ollama pull nomic-embed-text
```

Acceso:
- **Frontend UI:** [http://localhost:5173](http://localhost:5173)
- **Backend API & Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Qdrant Dashboard:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---

## 🛠️ Ejecución en Desarrollo Local

### 1. Backend (Python 3.12)

```bash
cd backend

# Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# Iniciar servidor FastAPI
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> **Nota:** El backend cuenta con tolerancia a fallos y fallback en memoria para Qdrant y FastEmbed ONNX, por lo que puede ejecutarse localmente de inmediato para desarrollo y tests unitarios.

### 2. Frontend (Vue 3 + Vite)

```bash
cd frontend

# Instalar dependencias
npm install

# Iniciar servidor de desarrollo con Hot Reload
npm run dev
```

El frontend estará disponible en `http://localhost:5173` y conectará automáticamente con el backend en el puerto 8000.

---

## 🧪 Pruebas Automatizadas

### Backend (Pytest)
Incluye validación de seguridad (MIME, magic bytes, path traversal, cuotas), chunking, BM25, Qdrant, RRF, detección de estimaciones y una **prueba de estrés asíncrona con un PDF sintético de 25 páginas**:

```bash
cd backend
.venv/bin/pytest tests/ -v
```

### Frontend (Vitest)
Pruebas unitarias de componentes reactivos (`SSEProgressBar`, `ChatPanel` con clics de citas):

```bash
cd frontend
npm run test:unit
```

---

## 📡 Referencia de la API REST

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/api/v1/documents/upload` | Carga de archivo PDF (`202 Accepted`), valida MIME y magic bytes. |
| `GET` | `/api/v1/documents` | Lista todos los documentos procesados y sus estados. |
| `GET` | `/api/v1/documents/{id}` | Metadatos detallados, conteo de chunks, imágenes y latencias por etapa. |
| `GET` | `/api/v1/documents/{id}/events` | Stream **SSE** en tiempo real del progreso de ingestión. |
| `GET` | `/api/v1/documents/{id}/file` | Descarga / streaming binario del PDF original. |
| `GET` | `/api/v1/documents/{id}/images` | Lista de figuras extraídas (`image_id`, `page_number`, `bbox`). |
| `GET` | `/api/v1/documents/{id}/images/{img_id}` | Obtiene el archivo binario de la imagen extraída. |
| `POST` | `/api/v1/chat/query` | Consulta RAG con búsqueda híbrida (RRF) y citaciones verificables. |
| `POST` | `/api/v1/vision/query` | Consulta multimodal a LLaVA 7B sobre una figura con detección de estimaciones. |
| `GET` | `/health` | Chequeo de estado del sistema y conectividad con Ollama. |

---

## 🔒 Seguridad y Observabilidad

- **Validación Estricta:** Comprobación de número mágico de cabecera (`%PDF-`) y tipo MIME `application/pdf`.
- **Mitigación Path Traversal:** Sanitización completa del nombre de archivo antes de escribir a disco (`sanitize_filename`).
- **Límite de Tamaño:** Límite configurable de 50 MB por archivo.
- **Aislamiento y Purga:** Borrado seguro de carpetas temporales y archivos corruptos en caso de excepción en la ingestión.
- **Logs Estructurados:** Formateo en JSON para integración con sistemas de observabilidad (ElasticSearch, Grafana Loki, Datadog).
- **Métricas de Latencia por Etapa:**
  - `extraction_time` (PyMuPDF)
  - `ocr_time` (Tesseract)
  - `chunking_time`
  - `embedding_time`
  - `indexing_time`
  - `retrieval_time` (Hybrid RRF)
  - `llm_time` (Qwen 2.5)
  - `vision_time` (LLaVA 7B)
