# RepoLens — GitHub Repository Analyzer

> Import any public GitHub repository and instantly get metadata, architecture analysis, source code browser, README renderer, and live activity feeds.

[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite)](https://sqlite.org)

## Features

| Feature | Description |
|---|---|
| **Repository Import** | Paste any public GitHub URL — downloads source, extracts all metadata |
| **Architecture Intelligence** | Framework detection, dependency graph, folder hierarchy, key file identification |
| **Source File Viewer** | Browse and view every source file with instant search and file-type icons |
| **README Viewer** | Rendered markdown documentation for every repository |
| **Live Activity Feed** | Recent commits, open issues, and pull requests fetched live from GitHub API |
| **Rich Metadata** | Stars, forks, language breakdown, repository size, owner info at a glance |
| **Beautiful Dashboard** | Multi-tab UI with dark/light theme, toast notifications, responsive design |

## Tech Stack

**Frontend**
- Next.js 15 + TypeScript
- Tailwind CSS
- react-markdown + remark-gfm

**Backend**
- FastAPI (Python 3.12)
- SQLite + SQLAlchemy (async)
- GitHub REST API
- Redis optional (caching — skips gracefully if absent)

**Infrastructure**
- Run natively — no Docker required
- Structured logging (structlog)

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- (Optional) GitHub personal access token for higher API rate limits
- (Optional) Redis for caching — app runs fine without it

### 1. Clone & Configure
```bash
git clone <your-repo>
cd you-are-my-senior-ai-engineer
cp .env.example .env
```

Edit `.env`:
```env
GITHUB_TOKEN=github_pat_...   # Optional but recommended
```

### 2. Start the Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
(On macOS/Linux use `source .venv/bin/activate`.)

> **Note:** Run uvicorn from the project **root** if you want it to pick up the root `.env`:
> `uvicorn app.main:app --app-dir backend --reload --port 8000`

### 3. Start the Frontend
Open a **second terminal**:
```bash
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs

### One-Command Start (Windows)

Just double-click or run `run.cmd` — it opens two windows (backend + frontend):

```bash
run.cmd
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GITHUB_TOKEN` | ❌ | — | GitHub PAT for higher rate limits |
| `DATABASE_URL` | ❌ | `sqlite+aiosqlite:///./data/repo_lens.db` | SQLite connection string |
| `REDIS_URL` | ❌ | `redis://localhost:6379/0` | Redis connection string (optional) |
| `BACKEND_CORS_ORIGINS` | ❌ | `http://localhost:3000` | Allowed CORS origins |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/repositories/import` | Import a public GitHub repository |
| `GET` | `/api/v1/repositories/{id}` | Get repository details |
| `GET` | `/api/v1/repositories/{id}/files` | List browsable source files |
| `GET` | `/api/v1/repositories/{id}/content?path=` | Read file content |
| `GET` | `/api/v1/repositories/{id}/readme` | Get README content |
| `GET` | `/api/v1/repositories/{id}/activity` | Get commits, issues, PRs |
| `POST` | `/api/v1/repositories/{id}/architecture` | Generate architecture analysis |
| `GET` | `/api/v1/repositories/{id}/architecture` | Get cached architecture |
| `GET` | `/api/v1/health` | Health check |

## Project Structure
```
you-are-my-senior-ai-engineer/
├── frontend/
│   ├── app/
│   │   ├── page.tsx        # Main dashboard with 4 feature tabs
│   │   ├── layout.tsx      # Root layout with SEO metadata
│   │   └── globals.css     # Dark/light theme with animations
│   └── components/         # Reusable UI components
├── backend/
│   └── app/
│       ├── api/routes/
│       │   ├── repositories.py  # Import, files, content, readme, activity
│       │   └── architecture.py  # Static architecture analysis
│       ├── services/
│       │   ├── architecture.py  # Static code analysis
│       │   ├── github.py        # GitHub API client
│       │   └── retrieval.py     # File reading utilities
│       ├── models.py            # SQLAlchemy ORM models
│       ├── schemas.py           # Pydantic request/response schemas
│       └── main.py              # FastAPI app + CORS + lifecycle
└── data/                   # SQLite DB + downloaded repos (auto-created, gitignored)
```

## Built for OpenAI Build Week

This project demonstrates:
- **Full-stack TypeScript/Python** architecture with clean separation of concerns
- **Zero-dependency local setup** — SQLite + optional Redis, runs without Docker
- **GitHub API integration** for live repository metadata and activity
- **Static code analysis** — framework detection, dependency parsing, structure mapping
- **Premium SaaS UI** — dark glassmorphism, responsive, file viewer with search
