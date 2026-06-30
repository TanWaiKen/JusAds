---
inclusion: always
---

# Project Structure

```
Langhub-main/
├── backend/                        # Python FastAPI backend
│   ├── langgraph_api.py            # Main API server (FastAPI + WebSocket)
│   ├── config.py                   # Centralized configuration (env vars)
│   ├── .env                        # API keys and secrets (do not commit)
│   │
│   ├── agent/                      # ★ Primary pipeline module (LangGraph)
│   │   ├── pipeline.py             # LangGraph compliance pipeline (StateGraph)
│   │   ├── pipeline_runner.py      # Runs pipeline + emits WebSocket events
│   │   ├── ws_manager.py           # WebSocket ConnectionManager
│   │   ├── s3_client.py            # S3 media storage client
│   │   ├── supabase_client.py      # Supabase persistence client
│   │   ├── fallback_queue.py       # Retry queue for failed S3/Supabase ops
│   │   ├── validators.py           # File size + quota validation
│   │   ├── models.py               # Pydantic models (CheckRecord, ViolationRecord)
│   │   ├── data_model.py           # ComplianceState dataclass
│   │   ├── routing.py              # Human decision routing logic
│   │   ├── utils.py                # MIME detection utilities
│   │   ├── clients.py              # Gemini + external API clients
│   │   ├── compliance_tools.py     # Compliance analysis tools
│   │   ├── remix_tools.py          # Remediation/remix tools
│   │   ├── prompts.py              # LLM prompt templates
│   │   ├── personas/               # Cultural persona definitions (JSON)
│   │   ├── scripts/                # Utility scripts (ingestion, testing)
│   │   └── tests/                  # Unit tests (pytest)
│   │
│   ├── migrations/                 # Supabase SQL migrations
│   │   └── 001_initial_schema.sql  # Tables: projects, compliance_checks, violations
│   │
│   ├── assets/                     # Runtime data (gitignored)
│   │   ├── uploads/                # Uploaded media files
│   │   ├── clips/                  # Extracted violation clips
│   │   ├── edits/                  # Remediated outputs
│   │   ├── results/                # JSON result files
│   │   └── fallback/               # Local fallback when Supabase is down
│   │
│   ├── archived/                   # ⚠️ DEPRECATED — do not use
│   │   ├── jusads_text_compliance/
│   │   ├── jusads_image_compliance/
│   │   ├── jusads_video_compliance/
│   │   ├── jusads_transcription/
│   │   └── jusads_remix_pipeline/
│   │
│   ├── requirements.txt            # Python dependencies
│   └── pytest.ini                  # Test configuration
│
├── frontend/                       # React SPA (Vite + TypeScript)
│   ├── src/
│   │   ├── App.tsx                 # Root component with routing
│   │   ├── main.tsx                # Entry point
│   │   ├── pages/                  # Route-level page components
│   │   │   ├── landing.tsx         # Public landing page
│   │   │   ├── dashboard.tsx       # Dashboard shell (layout + sidebar)
│   │   │   ├── home.tsx            # Dashboard home
│   │   │   ├── compliance.tsx      # Compliance checker page
│   │   │   ├── assets.tsx          # Asset management
│   │   │   ├── campaigns.tsx       # Campaign management
│   │   │   ├── trends.tsx          # Trend analytics
│   │   │   └── profile.tsx         # User profile
│   │   ├── components/             # Shared components
│   │   │   ├── ui/                 # shadcn/ui primitives (do not edit)
│   │   │   └── compliance/         # Compliance-specific components
│   │   │       ├── PipelineFlowView.tsx   # React Flow pipeline visualization
│   │   │       ├── ComparisonView.tsx     # Side-by-side original vs remix
│   │   │       ├── ViolationPlayer.tsx    # Video segment player
│   │   │       ├── ConnectionStatus.tsx   # WebSocket status indicator
│   │   │       └── ProjectSidebar.tsx     # History + active projects
│   │   ├── services/               # API service layer
│   │   │   ├── complianceApi.ts    # HTTP API functions + interfaces
│   │   │   └── complianceWebSocket.ts  # WebSocket client class
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── types/                  # Shared TypeScript interfaces
│   │   └── lib/                    # Utilities, auth config
│   ├── public/                     # Static assets (logos, images)
│   └── dist/                       # Production build output
│
├── erd.drawio                      # Entity-Relationship Diagram
├── class-diagram.drawio            # Backend class diagram
├── activity-pipeline.drawio        # Pipeline activity diagram
├── use-case.drawio                 # Use case diagram
├── system-architecture.drawio      # System architecture diagram
├── agentflow.drawio                # Agent flow diagram
│
└── .kiro/
    ├── steering/                   # AI assistant guidance files
    ├── skills/                     # GSAP animation skills
    └── specs/                      # Feature specifications
```

## Key Conventions

- **`backend/agent/`** is the primary module — all new backend code goes here.
- **`backend/archived/`** contains deprecated `jusads_*` modules — never import or reference.
- **Frontend UI components** in `components/ui/` are shadcn-generated — do not edit directly.
- **Compliance components** live in `components/compliance/` — domain-specific UI.
- **Pages** are flat files in `src/pages/` corresponding to routes.
- **Services** in `src/services/` handle all API communication (HTTP + WebSocket).
- **Assets directory** (`backend/assets/`) is runtime data — gitignored, never committed.
- **Diagrams** are `.drawio` files at project root — open with draw.io or VS Code extension.
