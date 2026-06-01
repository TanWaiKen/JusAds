# Tech Stack & Build System

## Backend (Python)

- **Framework**: FastAPI with uvicorn
- **AI/ML**: Google Gemini (multimodal analysis), LangGraph (workflow orchestration)
- **Cloud Services**: AWS (Transcribe for audio-to-text, S3)
- **Media Processing**: FFmpeg (video clip extraction)
- **Testing**: pytest
- **Key Libraries**: langgraph, python-multipart, google-generativeai

### Backend Commands

```bash
# Run the API server (from backend/)
uvicorn langgraph_api:app --reload --port 8000

# Run the simpler video-only API
uvicorn api:app --reload --port 8000

# Run video compliance check manually
python run_video_check.py

# Run tests
pytest
```

## Frontend (TypeScript / React)

- **Framework**: React 19 with TypeScript 6
- **Build Tool**: Vite 8
- **Styling**: Tailwind CSS 4 (via @tailwindcss/vite plugin)
- **UI Components**: shadcn/ui (Radix-based)
- **Routing**: react-router v7
- **Auth**: oidc-client-ts (AWS Cognito OAuth)
- **Charts**: Recharts
- **Icons**: Lucide React
- **Animation**: GSAP (use for professional, polished UI animations)
- **Theming**: next-themes (dark/light mode)

### Frontend Commands

```bash
# Development server (from frontend/)
npm run dev

# Production build
npm run build

# Lint
npm run lint

# Preview production build
npm run preview
```

## Path Aliases

- Frontend uses `@/` alias mapped to `./src/` (configured in vite.config.ts)

## Environment

- Backend `.env` file in `backend/` contains API keys (Gemini, AWS credentials)
- Frontend connects to backend API at localhost:8000
