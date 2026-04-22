# Codebase Explainer

Codebase Explainer ingests a GitHub repository, indexes its source code, and lets you ask grounded questions about the codebase through a FastAPI backend and a Next.js frontend.

Example questions:
- "Where is ingestion implemented?"
- "Explain the ingestion flow end to end."
- "What are the main entrypoints?"
- "Show the architecture or call flow."

## Features

- GitHub repository ingestion
- File tree fetch, content fetch, chunking, and embedding generation
- Grounded code Q&A with source references
- Overview, entrypoint, and architecture endpoints
- Next.js dashboard for ingest, re-ingest, ask, and analysis
- Ollama-first local setup
- Retrieval fallback for local MongoDB when Atlas vector search is unavailable

## Stack

### Backend
- FastAPI
- Motor / MongoDB
- Background ingestion jobs

### AI
- Ollama embeddings: `nomic-embed-text`
- Ollama chat model: `qwen2.5-coder:7b-instruct`
- Gemini optional fallback

### Frontend
- Next.js App Router
- React
- Proxy-based API access through `/backend/*`

## How Ingestion Works

1. `POST /api/v1/ingest` stores a repo document and creates an ingest job.
2. A background task reads the GitHub repo metadata and default branch.
3. The app fetches the repository tree and stores file metadata in `repo_files`.
4. It downloads text/code file contents into `repo_file_contents`.
5. It chunks those files and stores embeddings plus chunk metadata in `code_chunks`.
6. After that, the repo can be queried through `/ask`, `/overview`, `/entrypoints`, and `/architecture`.

## Question Answering Flow

1. The user sends a question to `POST /api/v1/repos/{repo_id}/ask`.
2. The system classifies the question intent.
3. Relevant chunks are retrieved.
   On MongoDB Atlas this uses vector search.
   On local MongoDB this falls back to keyword/path retrieval.
4. The LLM generates an answer using only retrieved repository context.
5. The API returns the answer plus source locations.

## Core Endpoints

| Endpoint | Description |
| --- | --- |
| `POST /api/v1/ingest` | Ingest a GitHub repository |
| `GET /api/v1/repos` | List ingested repositories |
| `GET /api/v1/jobs/{job_id}` | Inspect ingestion job status |
| `POST /api/v1/repos/{repo_id}/ask` | Ask a grounded code question |
| `GET /api/v1/repos/{repo_id}/overview` | Repository overview |
| `GET /api/v1/repos/{repo_id}/entrypoints` | Detected entrypoints |
| `GET /api/v1/repos/{repo_id}/architecture` | Architecture flows |
| `GET /api/v1/health` | Health check |

## Frontend

The Next.js UI supports:
- ingesting a repository
- re-ingesting an existing repository
- viewing job status
- asking grounded questions
- inspecting overview, entrypoints, and architecture output

Default local URLs:
- API: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Web: [http://127.0.0.1:3000](http://127.0.0.1:3000)

## Local Development

### Prerequisites

- Python 3.10+
- Node.js 22+
- MongoDB running locally on `mongodb://localhost:27017`
- Ollama running locally

### 1. Clone the repository

```bash
git clone https://github.com/nikhileshsirohi/codebase_explainer.git
cd codebase_explainer
```

### 2. Configure backend environment

Create `apps/api/.env` with values like:

```env
ENV=dev
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=codebase_explainer
GITHUB_TOKEN=
GEMINI_API_KEY=
MONGODB_VECTOR_INDEX=code_chunks_v1
LLM_PROVIDER=auto
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_MODEL=qwen2.5-coder:7b-instruct
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

`GITHUB_TOKEN` is optional for public repositories. If you set it, make sure it is valid.

### 3. Install backend dependencies

```bash
cd apps/api
pip install -e ".[dev]"
```

### 4. Start the backend

macOS / Linux:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Windows:

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Start Ollama

In another terminal:

```bash
ollama serve
ollama pull nomic-embed-text
ollama pull qwen2.5-coder:7b-instruct
```

### 6. Start the frontend

```bash
cd apps/web
npm install
API_ORIGIN=http://127.0.0.1:8000 npm run dev
```

### 7. Verify the backend

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "mongo": true,
  "ollama": true
}
```

## Docker Compose

The compose setup now includes:
- `mongo` on port `27017`
- `api` on port `8000`
- `web` on port `3000`

Start the stack:

```bash
cd infra/docker
docker compose up --build
```

Notes:
- The API container expects Ollama to be reachable at `http://host.docker.internal:11434`.
- Start Ollama on your host machine before using ingestion or question answering.

## Notes

- MongoDB Atlas vector search is optional, not required for local development.
- Local MongoDB uses keyword/path retrieval fallback for `/ask` and `/search`.
- Do not commit real secrets in `apps/api/.env`. Rotate any exposed tokens before pushing to GitHub.
