# Rexgent

> Give me a story idea. I'll hand you back a short drama.

Rexgent is an autonomous AI-powered short drama production pipeline built on **Qwen Cloud**. Type a one-line premise and Rexgent handles the rest — scriptwriting, character building, storyboarding, video generation, and iterative editing — all in a single workspace.

**Built for:** [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 2: AI Showrunner

---

## Demo

<!-- Replace with your actual demo video link before submission -->
[![Demo Video](https://img.shields.io/badge/Watch-Demo%20Video-red?style=for-the-badge&logo=youtube)](https://youtube.com)

**Demo flow (under 3 minutes):**

1. Paste a premise: *"A detective in 2047 Tokyo discovers her partner is an AI."*
2. Rexgent generates a 3-scene screenplay in real time
3. Plot gap detector flags an issue — AI fixes it in one click
4. Character cards appear with MBTI inference — upload a reference photo
5. Relationship graph renders (detective ↔ AI partner: trust → betrayal)
6. Storyboard generates with budget breakdown (Wan + HappyHorse split)
7. Video generation runs with live progress dashboard
8. ConsistencyGuard catches face drift → auto-retries → passes
9. User trims a scene, flags "lighting too bright", regenerates → approves
10. Final render: 45 seconds of coherent short drama from a one-liner

---

## What It Does

```
One-line premise
      │
      ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Script      │────▶│  Characters  │────▶│  Storyboard  │
│  Generation  │     │  + MBTI      │     │  + Budget     │
│  + Analysis  │     │  + Face Lock │     │  Allocation   │
└─────────────┘     └──────────────┘     └──────────────┘
                                               │
      ┌────────────────────────────────────────┘
      ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Video       │────▶│  Editing     │────▶│  Final       │
│  Generation  │     │  Loop        │     │  Render      │
│  + Guard     │     │  (Trim/Regen)│     │  + Export    │
└─────────────┘     └──────────────┘     └──────────────┘
```

| Stage | What Happens |
|-------|-------------|
| **Script** | Generate from premise or import PDF/Word. AI detects plot gaps, missing endings, and scores quality on 5 axes before spending tokens on video. |
| **Characters** | Auto-extract profiles with MBTI inference. Upload reference photos for face-lock via Qwen-VL. Build relationship graphs with plot evidence. |
| **Storyboard** | Shot-by-shot cinematic breakdown. TokenOptimizer scores scenes by emotional weight and allocates Wan 2.7 (hero) vs HappyHorse 1.1 (transitions) within the $40 budget. |
| **Generation** | Async video generation with ConsistencyGuard — frame-level face validation with auto-retry. Live progress via WebSocket. |
| **Editing** | Timeline editor with trim, flag, and regen. Qwen-Max surgically rewrites prompts based on user feedback. A/B comparison for every regen. |
| **Export** | FFmpeg stitches approved clips, adds captions from script dialogue, exports MP4 with production cost report. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend                              │
│           Next.js 14 (App Router) + React                │
│  Script Editor │ Character Engine │ Storyboard │ Editor  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS / WebSocket
┌──────────────────────▼──────────────────────────────────┐
│                API Gateway (FastAPI)                      │
│             Deployed on Alibaba Cloud ECS                │
│  /script  /characters  /storyboard  /generate  /edit    │
└──────────┬───────────────────────────────┬──────────────┘
           │                               │
┌──────────▼───────────┐     ┌─────────────▼──────────────┐
│   Orchestrator       │     │    MCP Tool Server          │
│   (Qwen-Max)         │     │  ScenePromptCraft           │
│   Narrative Memory   │     │  ConsistencyGuard           │
│   Graph              │     │  TokenOptimizer             │
│                      │     │  NarrativeJudge             │
│   AI Guardrails      │     │  PlotGapDetector            │
│   Layer              │     │  EndingEngine               │
└──────────┬───────────┘     └─────────────┬──────────────┘
           │                               │
┌──────────▼───────────────────────────────▼──────────────┐
│                   Qwen Cloud APIs                        │
│  Qwen-Max │ Qwen-VL │ Wan 2.7 │ HappyHorse 1.1         │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│               Alibaba Cloud Infrastructure               │
│  OSS (videos, images) │ RDS PostgreSQL │ ApsaraDB Redis  │
└─────────────────────────────────────────────────────────┘
```

---

## Qwen Cloud Integration

| Component | Qwen Model | Purpose |
|-----------|-----------|---------|
| Script generation + structuring | Qwen-Max | Generate and parse screenplays |
| Plot gap detection + ending analysis | Qwen-Max | Narrative intelligence layer |
| Character extraction + MBTI | Qwen-Max | Profile building from dialogue patterns |
| Face embedding + frame validation | Qwen-VL | Visual consistency across scenes |
| Storyboard + cinematic prompts | Qwen-Max | Shot breakdown + prompt DSL |
| Hero scene video | Wan 2.7 | High-quality 1080p for climax scenes |
| Draft + transition video | HappyHorse 1.1 | Fast generation with native audio |
| Video-to-video editing | HappyHorse 1.1 V2V | Surgical clip regeneration |
| Prompt rewriting | Qwen-Max | Incorporates user feedback into prompts |

### 6 Custom MCP Tools

| Tool | Innovation |
|------|-----------|
| `ScenePromptCraft` | Cinematic prompt DSL — structured intermediate representation enforcing cinematography rules before prompt generation |
| `ConsistencyGuard` | Frame-level face similarity validation using Qwen-VL embeddings with tiered retry strategies |
| `TokenOptimizer` | Budget-aware scene scoring — turns the $40 token constraint into a quality allocation feature |
| `NarrativeJudge` | LLM-as-critic — second Qwen-Max call scoring scripts on 5 axes, blocking generation if quality is too low |
| `PlotGapDetector` | Typed narrative problem detection with inline annotations (like code linting for scripts) |
| `EndingEngine` | Ending completeness checker with branching alternative generation |

### AI Guardrails

| Guardrail | What It Prevents |
|-----------|-----------------|
| `PromptSanitizer` | Text/number hallucination in video — strips dialogue, scene numbers, injects anti-text negative prompts |
| `JsonOutputValidator` | Malformed JSON, truncated responses, prompt leakage, suspicious repetition |
| `ClipQualityValidator` | Black frames, frozen video, wrong duration |
| `CostCircuitBreaker` | Budget overrun — hard stop at 85%, $2/shot cap, 15 retry limit |
| `InputSanitizer` | Prompt injection in user inputs |
| `PreGenerationValidator` | Missing character visuals, empty storyboards |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (recommended)
- [Qwen Cloud](https://www.qwencloud.com/) API key
- Alibaba Cloud account (OSS, RDS, Redis)

### Quick Start (Docker)

```bash
git clone https://github.com/RZRexton/Rexgent.git
cd Rexgent
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### Manual Setup

**Backend:**

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Celery worker** (separate terminal):

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

### Environment Variables

```bash
# Qwen Cloud
QWEN_API_KEY=your_qwen_api_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Alibaba Cloud OSS
OSS_ACCESS_KEY_ID=your_key_id
OSS_ACCESS_KEY_SECRET=your_secret
OSS_BUCKET_NAME=rexgent-assets
OSS_ENDPOINT=https://oss-ap-southeast-1.aliyuncs.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/rexgent
REDIS_URL=redis://localhost:6379/0

# App
SECRET_KEY=your_secret_key
ENVIRONMENT=development
```

---

## Project Structure

```
Rexgent/
├── backend/                    # FastAPI + Python 3.11
│   ├── app/
│   │   ├── main.py             # FastAPI app entry
│   │   ├── config.py           # Pydantic Settings
│   │   ├── database.py         # SQLAlchemy setup
│   │   ├── models/             # 12 ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── routers/            # API endpoints
│   │   ├── services/           # Business logic + Qwen API calls + guardrails
│   │   ├── orchestrator/       # Master orchestrator + Narrative Memory Graph
│   │   ├── mcp_tools/          # 6 custom MCP tools
│   │   ├── workers/            # Celery async tasks
│   │   └── websocket/          # Socket.IO real-time events
│   ├── prompts/                # 12 Qwen-Max system prompt templates
│   ├── migrations/             # Alembic database migrations
│   └── tests/                  # Backend test suite
├── frontend/                   # Next.js 14 + TypeScript
│   ├── app/                    # App Router pages
│   │   └── projects/[id]/      # Script → Characters → Storyboard → Generate → Edit → Export
│   ├── components/             # React components by feature
│   ├── hooks/                  # Custom React hooks
│   ├── stores/                 # Zustand state stores
│   └── lib/                    # API client, WebSocket, TypeScript types
├── docs/                       # Full documentation
│   ├── 01_PRODUCT_SPEC.md
│   ├── 02_ARCHITECTURE.md
│   ├── 03_DEVELOPMENT_PLAN.md
│   ├── 05_QWEN_PROMPTS.md
│   ├── 06_MCP_TOOLS.md
│   └── 08_NARRATIVE_MEMORY_GRAPH.md
├── docker-compose.yml
└── LICENSE                     # MIT
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, Tailwind CSS, shadcn/ui, Zustand, React Query, D3.js, Socket.IO client, Monaco Editor |
| Backend | FastAPI, Python 3.11, SQLAlchemy 2.0, Alembic, Celery, Redis |
| AI | Qwen-Max, Qwen-VL, Wan 2.7, HappyHorse 1.1 (all via Qwen Cloud) |
| Infrastructure | Alibaba Cloud ECS, OSS, RDS PostgreSQL, ApsaraDB Redis, SLB, CDN |
| Video Processing | FFmpeg |

---

## Deployment (Alibaba Cloud)

Backend deployed on **Alibaba Cloud ECS** (Singapore region, `ap-southeast-1`).

| Service | Alibaba Cloud Product |
|---------|----------------------|
| Compute | ECS (API + Celery workers) |
| Object Storage | OSS (videos, images, exports) |
| Database | RDS PostgreSQL 15 |
| Cache/Queue | ApsaraDB Redis |
| Load Balancer | SLB (HTTPS termination) |
| CDN | CDN (video delivery) |

**Proof of Alibaba Cloud deployment:** [`backend/app/services/oss_manager.py`](backend/app/services/oss_manager.py) — uses the `oss2` SDK to upload generated clips and exports to Alibaba Cloud OSS.

---

## Documentation

| Document | Contents |
|----------|---------|
| [Product Spec](01_PRODUCT_SPEC.md) | Full feature specification, 6 user flows, acceptance criteria |
| [Architecture](02_ARCHITECTURE.md) | System architecture, DB schema, API routes, deployment config |
| [Development Plan](03_DEVELOPMENT_PLAN.md) | Phase-by-phase build plan with all file paths |
| [Qwen Prompts](05_QWEN_PROMPTS.md) | All 12 Qwen-Max system prompt templates |
| [MCP Tools](06_MCP_TOOLS.md) | All 6 MCP tool specs with input/output schemas |
| [Narrative Memory Graph](08_NARRATIVE_MEMORY_GRAPH.md) | NMG design, read/write patterns, persistence |

---

## Hackathon Submission

| | |
|---|---|
| **Track** | Track 2 — AI Showrunner |
| **Platform** | [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) |
| **Deadline** | July 9, 2026 (2:00 PM Pacific Time) |
| **Demo Video** | [YouTube link] |
| **Blog Post** | [Blog link] |

### Judging Criteria Alignment

| Criterion | Weight | Rexgent Coverage |
|-----------|--------|-----------------|
| Innovation & AI Creativity | 30% | 6 custom MCP tools, Narrative Memory Graph, cinematic prompt DSL, LLM-as-critic, AI guardrails |
| Technical Depth & Engineering | 30% | Orchestrator architecture, async Celery pipeline, ConsistencyGuard, cost circuit breakers |
| Problem Value & Impact | 25% | Solves real creator pain: tool fragmentation, character drift, plot holes, budget waste |
| Presentation & Documentation | 15% | Full architecture docs, 12 prompt templates, production cost report |

---

## License

[MIT](LICENSE)
