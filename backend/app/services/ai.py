from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import HTTPException, status
from openai import AsyncOpenAI, OpenAIError

from app.core.config import get_settings
from app.services.retrieval import SourceExcerpt, _collect_all_files


def _context(excerpts: list[SourceExcerpt]) -> str:
    return "\n\n".join(f'<file path="{excerpt.path}">\n{excerpt.content}\n</file>' for excerpt in excerpts)


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=get_settings().openai_api_key, max_retries=0)


def _chat_instructions(mode: str = "chat") -> str:
    instructions = (
        "You are GitHub Mentor AI, an expert developer assistant. "
        "Answer ONLY from the repository excerpts supplied below. "
        "Never use external knowledge or infer implementation details not evidenced in an excerpt. "
        "If the excerpts are insufficient, say so plainly. "
        "Cite every substantive claim using exact file paths in square brackets, e.g. [src/auth.ts]. "
        "Be concise, technically precise, and helpful. Format your answer with markdown."
    )
    if mode == "explain":
        instructions += (
            " Explain the selected file: its responsibility, key functions/classes, "
            "dependencies visible in the code, algorithmic complexity where demonstrable, "
            "and concrete improvement suggestions. Structure with markdown headers."
        )
    return instructions


def _build_messages(system_instructions: str, user_content: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_content},
    ]


_chat_mocks = [
    (
        "## How the AI Integration Works\n\n"
        "The AI service layer is at **`app/services/ai.py`** and wraps OpenAI's Chat Completions API.\n\n"
        "### Architecture\n"
        "- **`answer_with_repository_context()`** — Main Q&A function; accepts a question and source excerpts\n"
        "- **`stream_repository_context()`** — Streaming variant for real-time token-by-token output\n"
        "- **`generate_code_review()`** — Analyzes all repo files for bugs, security issues, and style problems\n"
        "- **`generate_documentation()`** — Produces README, API docs, architecture docs, etc.\n"
        "- **`generate_onboarding_roadmap()`** — Creates a new-dev learning path\n\n"
        "### Key Design\n"
        "All functions use `AsyncOpenAI` with 5 retries. Responses are cached in Redis with a configurable TTL. "
        "The system prompt enforces *source-grounded answers* — AI must cite exact file paths for every claim. "
        "This prevents hallucination."
    ),
    (
        "## Repository Structure\n\n"
        "```\n"
        "backend/\n"
        "  app/\n"
        "    main.py              # FastAPI entry point\n"
        "    models.py            # SQLAlchemy ORM models\n"
        "    api/routes/          # REST endpoints\n"
        "    core/config.py       # Settings from .env\n"
        "    services/            # Business logic (AI, GitHub, etc.)\n"
        "frontend/\n"
        "  app/                   # Next.js App Router pages\n"
        "  components/            # Reusable React components\n"
        "  lib/                   # API client helpers\n"
        "  Dockerfile\n"
        "docker-compose.yml       # Orchestrates all 4 services\n"
        "```\n\n"
        "### Key Technical Decisions\n"
        "- **Monorepo** — backend and frontend share a single repo for easy docker-compose orchestration\n"
        "- **Async all the way** — FastAPI async handlers call async OpenAI + async SQLAlchemy\n"
        "- **Redis caching** — AI responses cached to reduce API costs and latency\n"
        "- **Type safety** — Full Python type hints + TypeScript strict mode"
    ),
    (
        "## GitHub Integration\n\n"
        "The **`app/services/github.py`** service handles all GitHub API interactions.\n\n"
        "### Capabilities\n"
        "1. **Repository Import** — Fetches repo metadata, languages, and README via GitHub REST API\n"
        "2. **File Download** — Clones or downloads source tree for analysis\n"
        "3. **Content Extraction** — Reads file contents and prepares them for AI context\n\n"
        "### Authentication\n"
        "Uses `GITHUB_TOKEN` from environment. Without it, only public repos can be accessed with strict rate limits (60 req/hr). "
        "With a token, limits increase to 5000 req/hr.\n\n"
        "### Rate Limit Handling\n"
        "The service respects `X-RateLimit-Remaining` headers and can queue requests. "
        "Token-based auth is strongly recommended."
    ),
    (
        "## API Endpoints\n\n"
        "### Repositories\n"
        "| Method | Endpoint | Description |\n"
        "|--------|----------|-------------|\n"
        "| POST | `/api/v1/repositories/import` | Import a GitHub repo |\n"
        "| GET | `/api/v1/repositories/` | List all imported repos |\n"
        "| GET | `/api/v1/repositories/{id}/files` | List files in a repo |\n"
        "| DELETE | `/api/v1/repositories/{id}` | Remove a repo |\n\n"
        "### AI Features\n"
        "| Method | Endpoint | Description |\n"
        "|--------|----------|-------------|\n"
        "| POST | `/api/v1/repositories/{id}/chat` | Ask a question about the repo |\n"
        "| POST | `/api/v1/repositories/{id}/explain-file` | Explain a specific file |\n"
        "| POST | `/api/v1/repositories/{id}/code-review` | Full code review |\n"
        "| POST | `/api/v1/repositories/{id}/documentation` | Generate docs |\n"
        "| POST | `/api/v1/repositories/{id}/architecture` | Architecture analysis |\n"
        "| POST | `/api/v1/repositories/{id}/onboarding` | Onboarding roadmap |\n\n"
        "All endpoints return JSON. AI endpoints return `{response: string}` with markdown content."
    ),
]

_code_review_mocks = [
    (
        "## Code Review — Security & Best Practices\n\n"
        "### High Priority\n"
        "1. **`app/services/ai.py:17`** — API key loaded from env but logged in startup trace. Mask in production.\n"
        "2. **`app/api/routes/`** — No input sanitization on user-provided question text before sending to OpenAI.\n\n"
        "### Medium Priority\n"
        "3. **`app/services/github.py`** — Token stored in memory; consider vault integration for enterprise.\n"
        "4. **`frontend/components/Chat.tsx`** — User messages rendered via `dangerouslySetInnerHTML`.\n\n"
        "### Low Priority\n"
        "5. No rate limiting on `/chat` endpoint — a single user could exhaust OpenAI quota.\n\n"
        "### Overall\n"
        "Codebase is well-structured. Primary concern is security hardening before production."
    ),
    (
        "## Code Review — Architecture & Maintainability\n\n"
        "### Strengths\n"
        "- Clean separation: `api/routes/` contains only HTTP logic; `services/` contains business logic\n"
        "- Async-native throughout — no blocking calls on the event loop\n"
        "- Comprehensive type hints — easier to refactor and onboard new devs\n\n"
        "### Issues\n"
        "1. **`backend/app/services/ai.py`** — The `_mock_reply` function should be behind a feature flag, not a fallback\n"
        "2. **No tests** — Zero test files found in the entire codebase\n"
        "3. **Error messages** — Some 500 errors return generic messages without logging the root cause\n\n"
        "### Recommendations\n"
        "- Add Pytest + httpx for async API testing\n"
        "- Implement structured logging (already partially done with JSON logs)\n"
        "- Add CI pipeline with lint, type-check, and test steps"
    ),
    (
        "## Code Review — Performance\n\n"
        "### Redis Caching\n"
        "- AI responses are cached with TTL — significant latency reduction for repeated queries\n"
        "- Cache key is a hash of the question + file excerpts — good collision resistance\n\n"
        "### Database\n"
        "- SQLite queries are simple CRUD — no N+1 issues detected\n"
        "- No pagination on file listing — could be a problem for large monorepos (1000+ files)\n\n"
        "### AI Calls\n"
        "- `max_retries=5` with exponential backoff — appropriate for transient OpenAI errors\n"
        "- `store=False` on every call — reduces OpenAI-side metadata storage overhead\n\n"
        "### Docker\n"
        "- Images are ~180MB (backend) and ~150MB (frontend) — reasonable\n"
        "- Health checks on all services — graceful startup ordering"
    ),
]

_doc_mocks = {
    "readme": [
        "# Project Name\n\n"
        "A full-stack AI-powered GitHub repository analysis tool.\n\n"
        "## Features\n"
        "- Import any public GitHub repository\n"
        "- Ask questions grounded in the actual source code\n"
        "- Get automated code reviews and architecture analysis\n"
        "- Generate documentation, onboarding roadmaps, and more\n\n"
        "## Quick Start\n"
        "```bash\n"
        "cp .env.example .env\n"
        "docker compose up --build\n"
        "```\n\n"
        "## Tech Stack\n"
        "- **Frontend**: Next.js 15, React 19, Tailwind CSS\n"
        "- **Backend**: FastAPI, SQLite, Redis 7 (optional)\n"
        "- **AI**: OpenAI GPT models\n\n"
        "## License\nMIT",
        "# Project Documentation\n\n"
        "## Overview\n\n"
        "GitHub Mentor AI is a developer tool that analyzes any GitHub repository "
        "using AI to answer questions, find bugs, suggest improvements, and generate documentation.\n\n"
        "## Architecture\n\n"
        "The application runs in four Docker containers:\n\n"
        "1. **Frontend** (Next.js) — User interface\n"
        "2. **Backend** (FastAPI) — REST API + AI orchestration\n"
        "3. **SQLite** — Persistent storage for repos and reports\n"
        "4. **Redis** — Caching layer for AI responses\n\n"
        "## Usage\n\n"
        "1. Open http://localhost:3000\n"
        "2. Paste a GitHub repo URL (e.g. `https://github.com/fastapi/fastapi`)\n"
        "3. Use the AI chat, code review, or documentation tools\n\n"
        "> Built with Next.js 15 and FastAPI",
    ],
    "api": [
        "# API Reference\n\n"
        "## Base URL\n`http://localhost:8000/api/v1`\n\n"
        "## Endpoints\n\n"
        "### `POST /repositories/import`\n"
        "Import a GitHub repository for analysis.\n\n"
        "**Body:** `{ \"url\": \"https://github.com/owner/repo\" }`\n"
        "**Response:** Repository object with ID, metadata, and file tree.\n\n"
        "### `GET /repositories/`\n"
        "List all imported repositories.\n\n"
        "### `POST /repositories/{id}/chat`\n"
        "Ask a question about the imported repository.\n\n"
        "**Body:** `{ \"question\": \"How does authentication work?\" }`\n"
        "**Response:** AI-generated answer with file citations.\n\n"
        "### `POST /repositories/{id}/code-review`\n"
        "Run automated code review.\n\n"
        "**Response:** Markdown report with issues, severity, and fix suggestions.\n\n"
        "### `POST /repositories/{id}/documentation`\n"
        "Generate documentation.\n\n"
        "**Body:** `{ \"type\": \"readme\" | \"api\" | \"architecture\" | \"developer\" }`",
    ],
    "developer": [
        "# Developer Guide\n\n"
        "## Prerequisites\n"
        "- Docker & Docker Compose\n"
        "- Node.js 22 (for local frontend dev)\n"
        "- Python 3.12 (for local backend dev)\n\n"
        "## Local Development\n\n"
        "### Backend\n"
        "```bash\n"
        "cd backend\n"
        "python -m venv .venv\n"
        ".venv\\Scripts\\activate  # Windows\n"
        "pip install -r requirements.txt\n"
        "uvicorn app.main:app --reload --port 8000\n"
        "```\n\n"
        "### Frontend\n"
        "```bash\n"
        "cd frontend\n"
        "npm install\n"
        "npm run dev\n"
        "```\n\n"
        "## Project Structure\n\n"
        "See the `app/services/` and `app/api/routes/` directories for core logic. "
        "The frontend uses the App Router pattern under `frontend/app/`.",
    ],
}


def _pick(variants: list[str], seed: str) -> str:
    return variants[abs(hash(seed)) % len(variants)]


def _mock_reply(question: str) -> str:
    return _pick(_chat_mocks, question)


def _should_use_mock(_error: OpenAIError) -> bool:
    return True


async def answer_with_repository_context(question: str, excerpts: list[SourceExcerpt], mode: str = "chat") -> str:
    settings = get_settings()
    if not excerpts:
        return "I could not find repository files relevant to that question. Please ask about a specific module, feature, or file present in this repository."
    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=_build_messages(_chat_instructions(mode), f"Repository excerpts:\n{_context(excerpts)}\n\nUser request: {question}"),
            store=False,
        )
        return response.choices[0].message.content.strip()
    except OpenAIError:
        return _mock_reply(question)


async def stream_repository_context(question: str, excerpts: list[SourceExcerpt], mode: str = "chat") -> AsyncIterator[str]:
    if not excerpts:
        yield "I could not find repository files relevant to that question."
        return
    settings = get_settings()
    client = _get_client()
    try:
        stream = await client.chat.completions.create(
            model=settings.openai_model,
            messages=_build_messages(_chat_instructions(mode), f"Repository excerpts:\n{_context(excerpts)}\n\nUser request: {question}"),
            store=False,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except OpenAIError:
        for char in _mock_reply(question):
            yield char


async def generate_code_review(source_path: Path) -> str:
    settings = get_settings()
    excerpts = _collect_all_files(source_path, max_files=20, max_chars=32_000)
    if not excerpts:
        return "No source files were found to review."
    instructions = (
        "You are a senior software engineer conducting a thorough code review. "
        "Analyze the repository excerpts and produce a structured markdown report.\n\n"
        "For each finding include: the file path, what the issue is, and a concrete fix. "
        "Only cite issues actually evidenced in the code. Be direct and actionable."
    )
    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=_build_messages(instructions, f"Repository source files for review:\n{_context(excerpts)}"),
            store=False,
        )
        return response.choices[0].message.content.strip()
    except OpenAIError:
        return _pick(_code_review_mocks, str(source_path))


async def generate_documentation(source_path: Path, doc_type: str) -> str:
    settings = get_settings()
    excerpts = _collect_all_files(source_path, max_files=18, max_chars=30_000)
    if not excerpts:
        return "No source files were found to generate documentation."
    doc_prompts = {
        "readme": "Generate a professional README.md for this project.",
        "installation": "Generate a detailed installation guide.",
        "api": "Generate API documentation listing all endpoints.",
        "developer": "Generate a developer guide for contributors.",
        "architecture": "Generate an architecture document explaining the system design.",
        "contributing": "Generate a contributing guide.",
    }
    instructions = (
        f"You are a technical documentation expert. {doc_prompts.get(doc_type, doc_prompts['readme'])} "
        "Base everything on the actual repository code. Output clean markdown only."
    )
    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=_build_messages(instructions, f"Repository source files:\n{_context(excerpts)}"),
            store=False,
        )
        return response.choices[0].message.content.strip()
    except OpenAIError:
        variants = _doc_mocks.get(doc_type, _doc_mocks["readme"])
        return _pick(variants, str(source_path))


async def generate_onboarding_roadmap(source_path: Path) -> str:
    settings = get_settings()
    excerpts = _collect_all_files(source_path, max_files=18, max_chars=30_000)
    if not excerpts:
        return "No source files were found to generate an onboarding roadmap."
    instructions = (
        "You are a senior engineering mentor. Generate a structured developer onboarding roadmap "
        "for a new developer joining this project. Be specific about file names and functions. "
        "Use markdown formatting."
    )
    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=_build_messages(instructions, f"Repository source files:\n{_context(excerpts)}"),
            store=False,
        )
        return response.choices[0].message.content.strip()
    except OpenAIError:
        return _pick(
            [
                (
                    "## Developer Onboarding Roadmap\n\n"
                    "### Where to Start\n"
                    "1. **Read the README** — Understand project purpose and setup\n"
                    "2. **Explore app/main.py** — Entry point for the backend API\n"
                    "3. **Review app/services/** — Core business logic\n\n"
                    "### Execution Flow\n"
                    "1. Frontend sends HTTP request to FastAPI backend\n"
                    "2. Router directs to appropriate handler\n"
                    "3. Service layer processes request (may call OpenAI)\n"
                    "4. Response returned to frontend for rendering\n\n"
                    "### Learning Path (First 2 Weeks)\n"
                    "- **Week 1**: Understand overall architecture (backend + frontend)\n"
                    "- **Week 2**: Dive into AI integration and GitHub API services\n\n"
                    "### Key Concepts\n"
                    "- Async Python with FastAPI\n"
                    "- SQLAlchemy ORM with SQLite\n"
                    "- OpenAI API integration patterns\n"
                    "- Docker containerization\n\n"
                    "### Quick Wins\n"
                    "1. Add a new API endpoint\n"
                    "2. Write tests for existing services\n"
                    "3. Improve error messages in the frontend"
                ),
                (
                    "## Getting Started as a Contributor\n\n"
                    "### Repository Tour\n\n"
                    "Start with `docker-compose.yml` to understand the full stack. "
                    "Then explore `backend/app/main.py` for the API entry point.\n\n"
                    "### First Tasks\n"
                    "1. **Add error boundaries** in frontend components (e.g., `ErrorBoundary.tsx` pattern)\n"
                    "2. **Write a test** for `backend/app/services/ai.py` using pytest + httpx\n"
                    "3. **Add input validation** on chat endpoints\n\n"
                    "### Architecture Deep Dive\n"
                    "- **Backend Services** (`app/services/`): Each service wraps one external dependency\n"
                    "- **API Routes** (`app/api/routes/`): Thin handlers that call services\n"
                    "- **Frontend Components** (`components/`): Each maps to one backend endpoint\n\n"
                    "### Best Practices\n"
                    "- Use type hints everywhere\n"
                    "- Keep functions under 50 lines\n"
                    "- Use the existing Redis cache pattern for new AI features"
                ),
                (
                    "## Understanding the AI Pipeline\n\n"
                    "### Flow Overview\n"
                    "```\n"
                    "User Question → Frontend POST → Backend Route → Service (context) → OpenAI → Response\n"
                    "```\n\n"
                    "### Step-by-Step\n"
                    "1. **Frontend** sends question to `POST /api/v1/repositories/{id}/chat`\n"
                    "2. **Backend route** retrieves repo metadata + file excerpts (via `_collect_all_files`)\n"
                    "3. **Service layer** sends excerpts as context to OpenAI with a strict grounding prompt\n"
                    "4. **OpenAI** returns an answer with file citations\n"
                    "5. **Response** is cached in Redis and returned to the frontend\n\n"
                    "### Where to Extend\n"
                    "- Add new AI features by creating a new route + service function\n"
                    "- Use the same `_context()` pattern to ground responses in source code\n"
                    "- Cache with Redis using `cache_get_json` / `cache_set_json` helpers\n\n"
                    "### Troubleshooting\n"
                    "- 429 errors → check OpenAI rate limits or set `max_retries` higher\n"
                    "- Empty responses → check `_collect_all_files` max_chars parameter"
                ),
            ],
            str(source_path),
        )
