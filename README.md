# AI-OCR Sprint: Sistema de RAG Multimodal sobre Documentos PDF Complejos

Sistema de grado productivo para procesamiento asíncrono, indexación híbrida y consulta conversacional multimodal sobre documentos PDF complejos (de 20 a cientos de páginas). Diseñado con arquitectura desacoplada mediante interfaces, búsqueda híbrida con Reciprocal Rank Fusion (RRF), citaciones verificables, streaming de respuestas en tiempo real e inspección visual con Moondream. Incluye una interfaz editorial suiza con visor de PDF, asistente RAG con streaming y búsqueda léxica de palabras clave.

---

## 🏛️ Arquitectura del Sistema

```
                         ┌──────────────────────────────────────────────┐
                         │              Frontend (Vue 3)                │
                         │   PdfViewer ─ ChatPanel ─ FigureGallery      │
                         │   KeywordSearch ─ ImageInspectorModal        │
                         └──────────────────────┬───────────────────────┘
                                                 │ SSE Stream / REST
                                                 ▼
                         ┌──────────────────────────────────────────────┐
                         │              Backend (FastAPI)               │
                         │      Asynchronous Ingestion Pipeline         │
                         │      Streaming RAG (SSE) + Keyword Search    │
                         └──────┬───────────────┬────────────────┬──────┘
                                │               │                │
            ┌───────────────────▼──┐     ┌──────▼────────┐   ┌───▼──────────────┐
            │ PyMuPDF (fitz) + OCR │     │ Qdrant Vector │   │ Ollama Inferencia│
            │ Extract Text, BBoxes │     │ Densa + BM25  │   │ Qwen 2.5 (Text)  │
            │ & Figures (PNG/JPEG) │     │ Híbrido (RRF) │   │ Moondream (Vision)│
            └──────────────────────┘     └───────────────┘   └──────────────────┘
```

### Características Principales

1. **Pipeline Asíncrono no bloqueante:**
   - La carga (`POST /api/v1/documents/upload`) responde inmediatamente con `202 Accepted` y `document_id`.
   - La máquina de estados (`uploaded` ➔ `extracting` ➔ `ocr_processing` ➔ `chunking` ➔ `indexing` ➔ `ready` | `failed`) emite eventos en tiempo real mediante **Server-Sent Events (SSE)** en `/api/v1/documents/{id}/events`.
   - **Subida resiliente:** el archivo se transfiere a disco directamente en chunks de 64 KB con validación progresiva de MIME, magic bytes y tamaño, sin agotar el buffer.
2. **Procesamiento de PDF y Multimodal:**
   - Extracción de texto estructurado y coordenadas `bbox` con **PyMuPDF (`pymupdf`)**.
   - Extracción automática de figuras e imágenes embebidas con metadatos de página (`image_id`, `page_number`, `bbox`, `width`, `height`).
   - **OCR Fallback** automático con Tesseract para páginas escaneadas o regiones sin texto vectorial nativo.
   - **Recuperación ante PDFs dañados:** reintento de apertura vía stream binario y extracción de respaldo en Python puro con `pypdf`.
3. **Búsqueda Híbrida y Fusión RRF:**
   - Combina búsqueda densa en **Qdrant** (embeddings vectoriales) y búsqueda léxica **BM25** (Okapi BM25).
   - Fusión mediante **Reciprocal Rank Fusion (RRF)**:
     $$RRF\_score(d) = \sum_{m \in M} \frac{1}{60 + r_m(d)}$$
   - Caché de recuperación para consultas repetidas.
4. **Streaming RAG en Tiempo Real (SSE):**
   - `POST /api/v1/chat/stream` ejecuta la recuperación híbrida y transmite la respuesta en flujo con eventos `citations`, `token`, `ttft`, `metrics` y `done`.
   - Metricas de **Time-To-First-Token (TTFT)** y rendimiento en `tokens/sec`.
   - Fallback automático a un extractor local si el proveedor LLM primario no responde.
5. **Citas Verificables y Anti-Alucinación:**
   - Generación de respuestas con **Qwen 2.5** basada estrictamente en los fragmentos de contexto.
   - Cada afirmación incluye citas con `page_number`, `chunk_id` y `snippet`.
   - Al hacer clic en una cita desde la interfaz, el visor de PDF navega instantáneamente a la página citada y la resalta.
6. **Búsqueda Léxica de Palabras Clave:**
   - `GET /api/v1/documents/{id}/search` permite búsqueda rápida de términos o frases con opciones `case_sensitive` y `exact`.
   - Devuelve coincidencias con `page_number`, `chunk_id`, `bbox`, `line_number` y snippet resaltado.
   - Un clic en un resultado salta al visor y resalta el fragmento exacto.
7. **Inspección Visual de Figuras con Moondream:**
   - Galería interactiva para consultar gráficos, esquemas y diagramas extraídos.
   - `POST /api/v1/vision/query` analiza la figura con **Moondream**, incorporando el texto circundante de la página como contexto.
   - **Detector de Estimación Numérica:** Identifica automáticamente si una respuesta sobre un gráfico contiene inferencias cuantitativas visuales y añade una advertencia destacada para prevenir alucinaciones numéricas.
8. **Tolerancia a Fallos:**
   - Proveyedores desacoplados mediante factory e interfaces en `app/services/providers`.
   - Fallback a implementaciones locales (in-memory) cuando Ollama, Qdrant o FastEmbed no están disponibles.

---

## 🎨 Frontend: Diseño Editorial Suizo

Interfaz Vue 3 + Vite con lenguaje visual **Swiss Editorial Design** (estilo tipográfico suizo): azul Klein `#0047FF`, esquinas a 0px, tipografía mono/Inter, modo claro y oscuro, y grid asimétrico 55% / 45%.

- **Barra superior técnica:** identidad del sistema, telemetría del documento activo (`nombre`, `page_count`, estado `ready`/procesando) y accesos rápidos.
- **Panel izquierdo (55%):** `PdfViewer` con overlays de coordenadas y highlight, más galería colapsable `FigureGallery` para saltar a figuras.
- **Panel derecho (45%) con tabs:**
  - `[ 01 // ASISTENTE RAG ]` — `ChatPanel` con streaming, citas clicables y métricas TTFT.
  - `[ 02 // BÚSQUEDA LÉXICA ]` — `KeywordSearch` con filtros `Aa` (mayúsculas) y `""` (palabra exacta).

  Acceso rápido por atajo `⌘K` / `Ctrl+K`.
- **Modales:** `DocumentUploader` (pre-flight: extensión, tamaño y magic bytes `%PDF-`) y `ImageInspectorModal` (consulta visual de figuras).
- **Progreso en vivo:** `SSEProgressBar` con stepper de las etapas de ingestión vía SSE.
- **Composables:** `useChat` (streaming), `useDocumentSSE` (progreso) y `usePdfViewer` (navegación/bbox).

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
docker exec -it pdf_rag_ollama ollama pull moondream
docker exec -it pdf_rag_ollama ollama pull nomic-embed-text
```

> **Nota:** En el `docker-compose.yml` el puerto de Ollama del host está mapeado como `11435:11434`, mientras que en desarrollo local se usa `http://localhost:11434`. El backend dentro de la red docker resuelve Ollama por nombre de contenedor (`http://ollama:11434`).

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

> **Nota:** El backend cuenta con tolerancia a fallos y fallback en memoria para Qdrant, FastEmbed ONNX y proveedores de inferencia, por lo que puede ejecutarse localmente de inmediato para desarrollo y tests unitarios — incluso sin Ollama, Qdrant ni Tesseract instalados.

> **Requisito adicional para OCR:** instalar el binario de Tesseract del sistema (p. ej. `apt install tesseract-ocr` en Debian/Ubuntu) para habilitar el OCR de páginas escaneadas.

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
Incluye validación de seguridad (MIME, magic bytes, path traversal, cuotas), chunking, BM25, Qdrant, RRF, streaming SSE, detección de estimaciones numéricas y una **prueba de estrés asíncrona con un PDF sintético de 25 páginas**:

```bash
cd backend
.venv/bin/pytest tests/ -v
```

Suit de tests:
- `test_security.py` — validación estricta de carga y path traversal.
- `test_chunking.py` — segmentación de texto y metadatos de página.
- `test_retrieval.py` — BM25, Qdrant (o fallback), híbrido y RRF.
- `test_search_and_stream.py` — búsqueda léxica y streaming SSE de chat.
- `test_vision.py` — análisis de figuras y detector de estimaciones.
- `test_async_stress.py` — PDF sintético de 25 páginas y pipeline asíncrono.

### Frontend (Vitest)
Pruebas unitarias de componentes reactivos (`SSEProgressBar`, `ChatPanel` con clics de citas, uploader, galería de figuras, inspector e inspector de imágenes y búsqueda léxica):

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
| `GET` | `/api/v1/documents/{id}/search` | Búsqueda léxica de palabras clave con `case_sensitive` y `exact`. |
| `POST` | `/api/v1/chat/query` | Consulta RAG con búsqueda híbrida (RRF) y citaciones verificables. |
| `POST` | `/api/v1/chat/stream` | Consulta RAG **streaming** vía SSE (`citations`, `token`, `ttft`, `metrics`, `done`). |
| `POST` | `/api/v1/vision/query` | Consulta multimodal a Moondream sobre una figura con detección de estimaciones. |
| `GET` | `/health` | Chequeo de estado del sistema y conectividad con Ollama. |

---

## 🔒 Seguridad y Observabilidad

- **Validación Estricta:** Comprobación de número mágico de cabecera (`%PDF-`) y tipo MIME `application/pdf`.
- **Pre-flight en cliente:** el frontend valida extensión, tamaño (≤ 50 MB) y cabecera `%PDF-` antes de enviar.
- **Mitigación Path Traversal:** Sanitización completa del nombre de archivo antes de escribir a disco (`sanitize_filename`).
- **Límite de Tamaño:** Límite configurable de 50 MB por archivo, reforzado durante el streaming de subida.
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
  - `vision_time` (Moondream)
  - `ttft` / `tokens_per_sec` / `token_count` / `total_time` (streaming RAG)

---

## 🆕 Novedades del Sprint

Resumen de las mejoras introducidas en esta iteración:

- **Streaming RAG en tiempo real:** nuevo endpoint `/api/v1/chat/stream` con Server-Sent Events; los tokens, citas, métricas y TTFT llegan en vivo a la interfaz (`ChatPanel`), con objetivo de latencia de primer token inferior a 1,2 s.
- **Búsqueda léxica de palabras clave:** nuevo endpoint `/api/v1/documents/{id}/search` y panel `KeywordSearch` con filtros de mayúsculas y palabra exacta; resultados con `bbox`/`line_number` que saltan al visor y resaltan el fragmento.
- **Rediseño editorial suizo:** nueva interfaz "Swiss Editorial Design" (gris + azul Klein), grid asimétrico 55/45, tabs de asistente RAG y búsqueda léxica, modo oscuro y atajo `⌘K`.
- **Subida resiliente:** carga de archivos en streaming por chunks de 64 KB con validación dinámica y sin agotar memoria; recuperación de PDFs dañados vía stream binario y fallback `pypdf`.
- **Modelo de visión Moondream:** sustitución de LLaVA 7B por el modelo ligero **Moondream** para la inspección visual de figuras (menor consumo y latencia), manteniendo el detector de estimaciones numéricas.
- **Tolerancia a fallos:** fallback automático a proveedores locales (LLM, visión, embeddings in-memory) cuando Ollama/Qdrant/FastEmbed no están disponibles, y caché de recuperación para consultas repetidas.
- **Más cobertura de pruebas:** tests nuevos para streaming SSE, búsqueda léxica, visión y componentes del frontend.

---

## 👥 Autores y Colaboradores

- **Diego Andrés Rodríguez Arrieta**
- **Violy Beatriz de la Rosa Solano**
- **Hector Mario Carvajal de los Reyes**