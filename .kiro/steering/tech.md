---
inclusion: always
---

# Tech Stack & Conventions

## Backend — Python 3 / FastAPI

### Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI + uvicorn (async ASGI) |
| AI/ML | Google Gemini (multimodal), LangGraph (StateGraph orchestration) |
| Cloud | AWS S3 (media storage), AWS Transcribe (audio-to-text), Supabase (persistence) |
| Vector DB | Qdrant (regulatory rules RAG) |
| Media | FFmpeg (video clips), ElevenLabs (TTS remediation) |
| Testing | pytest |

### Commands (run from `backend/`)

```bash
uvicorn langgraph_api:app --reload --port 8000   # Main API
uvicorn api:app --reload --port 8000              # Video-only API
pytest                                            # Tests
```

### Architecture Patterns

- **LangGraph pipelines**: Use `StateGraph` with `TypedDict` state, named nodes, and conditional edges for media-type routing. State must be a `TypedDict` — never a dataclass.
- **Resilient service init**: Wrap S3/Supabase/Qdrant initialization in try/except. Fall back to local storage on failure. Use `FallbackQueue` for deferred retry.
- **SSE streaming**: Use `StreamingResponse` with `media_type="text/event-stream"`. Each event is a JSON object containing at minimum: `node`, `status`, `data`.
- **WebSocket human-in-the-loop**: Use `ConnectionManager` + `asyncio.Event` for pipeline interrupts requiring user decisions.
- **Module naming**: Prefix all compliance modules with `jusads_` (e.g., `jusads_video_compliance`).
- **Secrets**: Load via `dotenv` from `backend/.env`. Centralize access in `config.py`. Never hardcode keys.
- **Logging**: Use `logging.getLogger(__name__)` at INFO level. Prefix messages with module context: `[ModuleName] message`.
- **Error handling**: All external service calls (Gemini, S3, Supabase, Qdrant, ElevenLabs) must be wrapped in try/except with meaningful error messages and graceful degradation.

### Code Style

- Type hints on all function signatures (parameters and return).
- `TypedDict` for LangGraph state — never dataclasses.
- `async def` for I/O-bound operations (network, file); `def` for CPU-bound graph nodes.
- Import order: stdlib → third-party → local.
- Docstrings on all public functions (one-liner minimum).

### Prohibitions

- No new dependencies without confirming an existing one doesn't cover the need.
- Never reference or import from `backend/archived/` — it contains deprecated code only.
- No runtime data in source-controlled directories. Use `backend/assets/` (gitignored).
- Never hardcode API keys or secrets.
- Never use dataclasses for LangGraph state definitions.
- Never use `print()` for logging — use the `logging` module.

## Frontend — TypeScript / React

### Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 19 + TypeScript 6 |
| Build | Vite 8 |
| Styling | Tailwind CSS 4 (`@tailwindcss/vite` plugin) |
| UI Components | shadcn/ui (Radix-based) |
| Routing | react-router v7 |
| Auth | oidc-client-ts (AWS Cognito OAuth) |
| Charts | Recharts |
| Icons | Lucide React |
| Animation | GSAP 3.15 + `@gsap/react` |
| Theming | next-themes (dark/light) |
| Testing | Vitest (`--run` flag only), fast-check (property-based) |

### Commands (run from `frontend/`)

```bash
npm run dev       # Dev server
npm run build     # Production build (tsc → vite)
npm run lint      # Lint
npm run test      # Tests (single run, never watch)
```

### Architecture Patterns

- **Path alias**: `@/` maps to `./src/`. Always use `@/` for project imports — never relative paths that escape `src/`.
- **Pages**: One component per file in `src/pages/`, each matching a route. Dashboard uses nested `<Route>` + `<Outlet>`.
- **Services**: All API calls live in `src/services/`. Use `fetch` + `FormData` for uploads. Parse SSE via `ReadableStream` line-by-line.
- **Components**: Shared components in `src/components/`. Files in `src/components/ui/` are shadcn-generated — never edit them directly. To customize, wrap in a new component outside `ui/`.
- **Types**: Define interfaces near usage in service files. Export shared/cross-module types from `src/types/`.
- **State management**: React hooks + context only. No external state libraries.
- **API base URL**: Read from `import.meta.env.VITE_API_BASE`, fallback to `http://localhost:8000`.

### Code Style

- Named exports for components; default export only for page components.
- `interface` over `type` for object shapes.
- Functional components only — no class components.
- File naming: `camelCase.ts` for services/utilities, `kebab-case.tsx` for components.
- Explicit return types on exported functions; inferred types acceptable for internal helpers.
- Destructure props in function parameters.

### Prohibitions

- Never edit files in `src/components/ui/` manually — use shadcn CLI to regenerate.
- No class components.
- No external state libraries (Redux, Zustand, etc.).
- No `any` type — use `unknown` + narrowing or define a proper interface.
- Never run Vitest in watch mode — always use `--run`.
- No inline styles — use Tailwind utility classes.

## Environment & Integration

- Backend `.env` holds keys for: Gemini, AWS, Supabase, ElevenLabs, Qdrant. Reference by name only — never expose values in code or output.
- Frontend connects to backend at `http://localhost:8000` (override via `VITE_API_BASE`).
- CORS: `allow_origins=["*"]` in dev only. Must be restricted in production.
- Upload limit: 100 MB per file. S3 user quota: 5 GB.
- Uploads go to S3 under a user-scoped prefix. Local fallback: `backend/assets/uploads/`.

## Decision Rules

When choosing how to implement something, apply these in order:

1. **Existing pattern wins**: If the codebase already does something a certain way, follow that pattern.
2. **Existing dependency wins**: Before adding a new package, check if an installed one covers the need.
3. **Backend vs. frontend logic**: Compliance logic, AI calls, and file processing belong in the backend. The frontend handles presentation and user interaction only.
4. **New compliance module**: Create under `backend/jusads_{name}/` with step-based files (`step1_*.py`, `step2_*.py`, etc.) and a top-level orchestrator.
5. **New frontend page**: Add a file in `src/pages/`, register the route in `App.tsx`, and add navigation in the dashboard sidebar.
