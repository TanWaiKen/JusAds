# JusAds — AI-Powered Advertising Compliance Platform

JusAds checks creative assets (video, image, audio, text) against cultural and regulatory guidelines for Southeast Asian markets. It provides automated compliance analysis, violation detection, risk scoring, and remediation suggestions.

## Tech Stack

| Layer | Frontend | Backend |
|-------|----------|---------|
| Framework | React 19 + TypeScript | FastAPI + Uvicorn |
| Build | Vite 8 | Python 3 |
| Styling | Tailwind CSS 4 + shadcn/ui | — |
| AI/ML | — | Google Gemini, LangGraph |
| Database | — | Supabase (Postgres) |
| Vector DB | — | Qdrant |
| Storage | — | AWS S3 |
| Testing | Vitest + fast-check | pytest |

## Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+
- API keys configured in `backend/.env` (Gemini, AWS, Supabase, ElevenLabs, Qdrant)

## Getting Started

### 1. Clone the repository

```bash
git clone <repo-url>
cd Langhub-main
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in `backend/` with the required API keys (see `backend/.env.example` or ask your team lead for values).

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

## Running the Application

### Start the Backend (API Server)

```bash
cd backend
uvicorn langgraph_api:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### Start the Frontend (Dev Server)

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173` and connects to the backend at `http://localhost:8000`.

## Available Commands

### Backend (`backend/`)

| Command | Description |
|---------|-------------|
| `uvicorn langgraph_api:app --reload --port 8000` | Start API server with hot reload |
| `pytest` | Run all backend tests |

### Frontend (`frontend/`)

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Production build (TypeScript check + Vite) |
| `npm run lint` | Run ESLint |
| `npm run test` | Run tests (single run, no watch) |
| `npm run preview` | Preview production build locally |

## Project Structure

```
Langhub-main/
├── backend/                    # Python FastAPI backend
│   ├── langgraph_api.py        # Main API server
│   ├── agent/                  # LangGraph pipeline + services
│   │   ├── pipeline.py         # Compliance pipeline (StateGraph)
│   │   ├── pipeline_runner.py  # Pipeline execution + WebSocket events
│   │   ├── supabase_client.py  # Database persistence
│   │   ├── s3_client.py        # Media storage
│   │   └── tests/              # Backend tests
│   ├── migrations/             # Supabase SQL migrations
│   └── requirements.txt        # Python dependencies
│
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── pages/              # Route-level pages
│   │   ├── components/         # Shared + domain components
│   │   ├── hooks/              # Custom React hooks
│   │   ├── services/           # API + WebSocket clients
│   │   ├── types/              # TypeScript interfaces
│   │   └── lib/                # Utilities
│   └── package.json
│
└── .kiro/                      # AI assistant specs + steering
```

## Key Workflows

1. **Upload** — Submit a media file or text ad for compliance checking
2. **Check** — Real-time pipeline progress via WebSocket (node-by-node status)
3. **Human Review** — Approve or request edits when the pipeline pauses for review
4. **Review** — View compliance results, violations, and risk scores
5. **Remix** — Automated remediation suggestions for non-compliant content
6. **Compare** — Side-by-side original vs. remediated output

## Environment Variables

The backend requires a `.env` file with keys for:

- `GOOGLE_API_KEY` — Gemini AI
- `SUPABASE_URL` / `SUPABASE_KEY` — Database
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — S3 storage
- `ELEVENLABS_API_KEY` — TTS remediation
- `QDRANT_URL` / `QDRANT_API_KEY` — Vector search

The frontend uses `VITE_API_BASE` to override the backend URL (defaults to `http://localhost:8000`).

## License

Private — internal use only.
