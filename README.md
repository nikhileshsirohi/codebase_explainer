# Codebase Explainer 🧠📦

Codebase Explainer is a **developer-focused backend system** that ingests a GitHub repository, indexes its source code, and allows you to **ask natural-language questions about the codebase** such as:

- “Where is ingestion implemented?”
- “Explain the ingestion flow end-to-end”
- “What are the main entrypoints?”
- “Show the architecture / call flow”

It is designed to work reliably on **real-world codebases**, not toy examples.

---

## ✨ Key Features

- GitHub repository ingestion
- Code chunking & vector embeddings
- Semantic + keyword fallback retrieval
- Intent-aware question routing
- Architecture & entrypoint analysis
- Works fully **locally** using Ollama
- JSON-first responses (developer friendly)

---

## 🧰 Technology Stack

### Backend
- **FastAPI** – REST API framework
- **MongoDB Atlas** – document store + vector search
- **Motor** – async MongoDB driver

### AI / ML
- **Ollama**
  - `nomic-embed-text` → embeddings
  - `qwen2.5-coder:7b-instruct` → LLM
- **Gemini** (optional / fallback)

### Code Intelligence
- Python AST parsing
- Custom symbol extraction
- Call-graph & pipeline detection
- Intent classification (flow / API / ingestion / search)

### Dev & Ops
- Docker
- Uvicorn
- Ruff (linting)
- Async background jobs

---

## 🏗 High-Level Architecture

---

## 🔁 Ingestion Flow

1. User submits a **GitHub repo URL**
2. `/ingest` API creates:
   - repo document
   - ingest job
3. Background worker:
   - fetches repo files
   - skips non-code files
   - chunks code by lines
   - generates embeddings
   - stores chunks in `code_chunks`
4. Repo becomes queryable

---

## 💬 Question Answering Flow

1. User asks a question (`/ask`)
2. System:
   - classifies intent (flow, API, ingestion, GitHub, generic)
   - retrieves relevant chunks (vector + fallback)
   - extracts symbols & pipeline hints
3. LLM generates a **grounded answer**
4. Response includes:
   - answer
   - exact source locations

---

## 🔍 Analysis APIs

### `/overview`
Summarizes:
- components
- tech stack
- data flow

### `/entrypoints`
Detects:
- FastAPI app startup
- API routes
- background jobs

### `/architecture`
Builds:
- call graph
- entrypoint → execution paths

---

## 🌐 API Endpoints (Core)

| Endpoint | Description |
|--------|------------|
| `POST /api/v1/ingest` | Ingest a new GitHub repo |
| `POST /api/v1/repos/{repo_id}/ask` | Ask questions |
| `GET /api/v1/repos/{repo_id}/overview` | Repo overview |
| `GET /api/v1/repos/{repo_id}/entrypoints` | Entrypoints |
| `GET /api/v1/repos/{repo_id}/architecture` | Architecture |
| `GET /health` | System health |

---

## 🖥 UI

- Simple HTML UI
- JSON-first responses
- Two ingestion modes:
  - New repo ingestion
  - Re-ingest selected repo
- Designed for **debuggability first**

---

## 🧪 Why JSON Output?

This is intentional.

- Exposes correctness issues early
- Easy to debug & extend
- Suitable for:
  - CLI tools
  - VS Code extensions
  - Future UI layers

Pretty UI can be added later **without changing the backend**.

---

## 🚀 How to Run

### Prerequisites
- Docker
- Docker Compose

```bash
docker compose up --build
docker exec -it codebase_explainer_ollama ollama pull nomic-embed-text
docker exec -it codebase_explainer_ollama ollama pull qwen2.5-coder:7b-instruct

curl http://localhost:8000/docs
```
## How to run (Without Docker)

```bass
https://github.com/nikhileshsirohi/codebase_explainer.git
cd codebase_explainer
```
### Install Backend Dependencies
```bash
cd apps/api
pip install -e ".[dev]"
```

### Start the FastAPI Server
***macOS / Linux***
```bash
python -m uvicorn app.main:app --reload --port 8000
```

***Windows***
```bash
uvicorn app.main:app --reload --port 8000
```
***The API will be available at:***
```bash
http://127.0.0.1:8000
```

### START Ollama (Required)
*** In another terminal ***
```bash
ollama serve
ollama pull nomic-embed-text
ollama pull qwen2.5-coder:7b-instruct
```

***Verify Is everything running***
```bash
curl http://127.0.0.1:8000/health
```

***Expected response***
{
  "status": "ok",
  "mongo": true,
  "ollama": true
}