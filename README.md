# Rexgent

> Give me a story idea. I'll hand you back a finished vertical episode.

Rexgent is an **autonomous AI showrunner** built on **Qwen Cloud**. Type a one-line premise and an agent runs the whole production: script, self-critique and revision, casting, storyboarding, budget allocation, video generation, dialogue, and a final 9:16 episode with burned-in subtitles — while a live dashboard shows every token and cent it spends.

**Built for:** [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 2: AI Showrunner

---

## What a run looks like

1. Create a drama: premise + genre + format (9:16 vertical) + a **spend cap** — a live panel projects the tokens and dollars this drama will cost before anything runs
2. Flip **Full Auto** and watch the agent: write → judge (8 axes incl. hook strength) → revise with the judge's own critique → extract characters → storyboard
3. The **beat sheet** shows the ladder: logline → scene beats, with the 3-second hook and the cliffhanger tagged
4. Casting builds the **production bible**: identity plates, per-outfit costume plates, location plates, one style plate, a voice per character
5. The **set dresser** pins each scene's props — and tracks state ("from shot 3: the vase lies shattered")
6. Budget allocation **fits the plan to the cap**: hook shots protected on Wan 2.7, supporting shots downgraded to HappyHorse, the least important deferred — all visible
7. Generation runs live: every clip shows its **reference provenance** (the exact plates that conditioned it) and a continuity score from real ArcFace embeddings
8. The **token dashboard** shows the engineering: most tokens ran on qwen-flash, Qwen-Max only wrote
9. Export renders itself: dialogue placed on the exact shots that speak it, BGM ducking under speech, captions burned in, vertical 1080×1920
10. One premise in → one watchable episode out, with a production report proving it stayed under budget

---

## The Autonomous Agent

A real LangGraph state machine — not a linear script. The judge can reject a draft and the rewrite receives the judge's actual critique as revision notes.

```mermaid
flowchart LR
    START((premise)) --> W[write script]
    W --> J{judge<br/>8 axes}
    J -- "weak hook / flat ending" --> R[revise with<br/>judge critique]
    R --> W
    J -- pass --> X[extract<br/>characters]
    X --> C{clarify}
    C -- "ambiguous" --> PAUSE([ask the user,<br/>resume on answer])
    C -- clear --> SB[storyboard<br/>+ set dresser]
    SB --> CAST[casting:<br/>bible plates + voices]
    CAST --> AUD[dialogue TTS]
    AUD --> B[budget: fit plan<br/>to spend cap]
    B --> V[generate video<br/>per-shot references]
    V --> E[auto export:<br/>9:16 + subtitles]
    E --> DONE((episode))
```

Plan-only by default (nothing is spent until you approve); **Full Auto** runs the whole graph and the finished episode renders itself the moment the last clip lands.

---

## Maximizing Quality Under a Token Budget

The track's core constraint, treated as an engineering problem:

| Lever | How Rexgent does it |
|-------|--------------------|
| **Model tiering** | A `ModelRouter` sends each task to the cheapest capable Qwen tier: **qwen-max only writes** (script, storyboard), **qwen-plus judges** (narrative judge, plot gaps, prompt craft), **qwen-flash does deterministic work** (structuring, extraction, wardrobe, set dressing, titles) |
| **Attribution** | Every LLM call lands on the drama's cost ledger with its model and task — spend per stage, per tier, live |
| **Structured output** | Native JSON mode with graceful fallback + array unwrapping; truncation retry; trailing-comma repair |
| **Context compression** | Non-creative agents receive a scene digest, not the full script JSON |
| **Adaptive allocation** | `TokenOptimizer` scores every shot's narrative importance, protects the hook (the opening shots that stop the scroll) on Wan 2.7, and **fits the plan to the user's spend cap**: downgrade least-important Wan shots to HappyHorse, then defer what still doesn't fit |
| **Visible** | A live token dashboard on the Generate page: tokens vs cap, per-model tier chips, cheap-tier share, per-stage bars |

---

## The Consistency Engine

The #1 quality problem in AI video is drift — faces, outfits, and rooms that change between shots. Rexgent's production bible conditions every clip, and makes it **provable**:

- **Identity plates + per-outfit costume plates** (image-edited *from* the face so identity carries), **location plates**, one **style plate** per drama
- **Reference stacks** per shot, in a deliberate order: identity → scene costume → previous-shot frame → scene anchor frame → location (wide shots only) → style
- **Set dresser**: per scene, the props every shot must render identically — with **prop state tracking** (a vase broken in shot 3 stays broken in shot 4; the pristine location plate is dropped once the state changes)
- **Deterministic seeds** per shot (same shot, same seed — re-renders differ only by what you changed)
- **Continuity scoring** after every clip: real ArcFace embeddings (insightface) + a Qwen-VL outfit/background check; weak clips are flagged for review, never silently shipped
- **Provenance on screen**: every clip tile shows the exact reference images that conditioned it

---

## Architecture

```mermaid
flowchart TB
    subgraph FE[Frontend — Next.js 14]
        UI[Script · Characters · Storyboard · Generate · Export]
        TD[Live token + cost dashboard]
        SM[Story map · Beat sheet · Bible panels]
    end
    FE <-- "HTTP + Socket.IO" --> API

    subgraph API[FastAPI + Socket.IO]
        AG[LangGraph agent]
        RT[Stage routers]
    end

    subgraph TOOLS[Shared tool registry — HTTP and MCP stdio]
        NJ[narrative_judge] & PG[plot_gap_detector] & EE[ending_engine]
        TO[token_optimizer] & SP[scene_prompt_craft] & SD[set_dresser] & CG[consistency_guard]
    end
    API --> TOOLS

    subgraph WK[Celery workers]
        GEN[generation runner<br/>reference stacks · seeds · continuity]
        CASTW[casting worker<br/>bible plates · voices]
        EXP[export worker<br/>stitch · captions · audio mix]
    end
    API --> WK

    subgraph QWEN[Qwen Cloud / DashScope intl]
        LLM[qwen-max · qwen-plus · qwen-flash]
        VID[wan2.7 t2v/i2v · happyhorse-1.1 t2v/i2v/r2v]
        IMG[wan2.6-t2i · qwen-image-edit-max]
        VL[qwen3-vl-plus] & TTS[qwen3-tts-flash · voice cloning]
    end
    TOOLS --> LLM
    WK --> QWEN

    subgraph INFRA[Infrastructure]
        PG2[(PostgreSQL + pgvector)] & RD[(Redis)] & OSS[(Alibaba OSS)] & N4J[(Neo4j)]
    end
    API --> INFRA
    WK --> INFRA
```

---

## Qwen Cloud Integration

| Component | Qwen Model | Purpose |
|-----------|-----------|---------|
| Script + storyboard writing | Qwen-Max | The only creative-writing tier |
| Judging, plot gaps, endings, prompt craft | Qwen-Plus | Analysis at a third of the cost |
| Structuring, extraction, wardrobe, set dressing, titles | Qwen-Flash | Deterministic JSON work, ~15x cheaper output |
| Hero + hook shots | Wan 2.7 (t2v/i2v) | Premium 1080P, native 9:16, seeded |
| Supporting shots | HappyHorse 1.1 (t2v/i2v/r2v) | Reference-to-video with up to 9 reference images |
| Clip surgery (regen loop) | HappyHorse 1.0 video-edit | Video-to-video fixes from user flags |
| Bible plates | wan2.6-t2i + qwen-image-edit-max | Costume plates edited FROM the face so identity carries |
| Continuity vision check | qwen3-vl-plus | Outfit + background scoring per clip |
| Dialogue | qwen3-tts-flash + voice enrollment | Preset voices per character, or clone from a sample (realtime WS) |

### 7 Custom Tools — one registry, two transports

Served identically over FastAPI HTTP **and** a real MCP stdio server (official `mcp` SDK), from one shared registry ([`backend/app/mcp_tools/registry.py`](backend/app/mcp_tools/registry.py)):

| Tool | Innovation |
|------|-----------|
| `NarrativeJudge` | LLM-as-critic on 8 axes including **hook_strength** and **cliffhanger_pull** — a weak opening blocks generation and drives the revision loop |
| `TokenOptimizer` | Budget fitting, not budget reporting: hook protection, tier downgrades, deferrals — the plan always fits the cap |
| `SetDresser` | Persistent set dressing + prop **state** tracking per scene (a broken vase stays broken) |
| `ScenePromptCraft` | Cinematic prompt DSL with anti-text sanitization, DoF-by-framing rules, and scene-setting injection |
| `ConsistencyGuard` | Face verification via real ArcFace embeddings with VLM diagnosis |
| `PlotGapDetector` | Typed narrative problem detection — like linting for scripts |
| `EndingEngine` | Ending completeness + branching alternatives |

### AI Guardrails

| Guardrail | What It Prevents |
|-----------|-----------------|
| `PromptSanitizer` | Text/number hallucination in video — strips quotes, scene numbers, names; injects anti-text negative prompts |
| `CostCircuitBreaker` | Budget overrun — hard stop at 85% of the drama's own spend cap |
| `InputSanitizer` | Prompt injection in user inputs |
| `PreGenerationValidator` | Missing character visuals, empty storyboards — blocks before spending |
| Continuity review queue | Weak clips flagged `NEEDS_REVIEW`, never silently shipped (and never retry-spammed) |

---

## Getting Started

### Prerequisites

- Python 3.11+ · Node.js 20+ · Docker & Docker Compose
- [Qwen Cloud](https://www.qwencloud.com/) API key (international / dashscope-intl)
- Alibaba Cloud OSS bucket

### Quick Start (Docker)

```bash
git clone https://github.com/RZRexton/Rexgent.git
cd Rexgent
cp backend/.env.example backend/.env   # add your keys
docker-compose up --build              # api + worker + frontend + postgres + redis + neo4j
```

- Frontend: http://localhost:3000 · API: http://localhost:8000 · API docs: http://localhost:8000/docs

### Manual Setup

```bash
# backend
cd backend
pip install -r requirements.txt
cp .env.example .env                   # add your keys
alembic upgrade head
uvicorn app.main:socket_app --reload --port 8000

# celery worker (separate terminal — generation/casting/export run here)
celery -A app.workers.celery_app worker --loglevel=info

# frontend
cd frontend && npm install && npm run dev
```

### Environment Variables

```bash
QWEN_API_KEY=your_qwen_api_key
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
OSS_ACCESS_KEY_ID=... / OSS_ACCESS_KEY_SECRET=... / OSS_BUCKET_NAME=... / OSS_ENDPOINT=...
DATABASE_URL=postgresql://user:password@localhost:5432/rexgent
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your_secret_key
```

### Deploy (Alibaba Cloud ECS)

One instance runs everything via the production compose base (the dev overlay
is only loaded locally):

```bash
# on an Ubuntu 22.04 ECS instance (>= 2 vCPU / 8 GB, ap-southeast-1), ports 3000 + 8000 open
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
git clone https://github.com/RZRexton/Rexgent.git && cd Rexgent
# copy your backend/.env onto the server (scp) — never commit it

export PUBLIC_API_URL="http://<server-ip>:8000"      # baked into the frontend build
export FRONTEND_ORIGIN="http://<server-ip>:3000"     # added to CORS (HTTP + websocket)
docker compose -f docker-compose.yml up -d --build
```

Migrations run automatically on backend start. Open `http://<server-ip>:3000`.
With a domain, put Caddy or Nginx in front for HTTPS and set both URLs to the
https origin instead.

### MCP Server (real Model Context Protocol)

The 7 tools are served over the **real MCP protocol** (official Python SDK, stdio), so any MCP client — Claude Desktop included — can discover and call Rexgent's showrunner tools:

```bash
cd backend
python -m venv .venv-mcp && .venv-mcp/Scripts/activate   # own venv: the mcp SDK pins starlette
pip install -r mcp_requirements.txt
python mcp_server_entry.py
```

Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "rexgent": {
      "command": "C:/path/to/Rexgent/backend/.venv-mcp/Scripts/python.exe",
      "args": ["C:/path/to/Rexgent/backend/mcp_server_entry.py"]
    }
  }
}
```

---

## Project Structure

```
Rexgent/
├── backend/                    # FastAPI + Python 3.11
│   ├── app/
│   │   ├── agent/              # LangGraph pipeline (graph, state, ops)
│   │   ├── models/             # 18 ORM models (bible, clips, cost events, ...)
│   │   ├── routers/            # API endpoints per stage
│   │   ├── services/           # model router · reference stacks · set dresser ·
│   │   │                       # generation runner · stitcher · cost ledger · guardrails
│   │   ├── mcp_tools/          # 7 shared tools (HTTP + MCP)
│   │   ├── mcp_server/         # real MCP stdio server (official SDK)
│   │   ├── workers/            # Celery: generation, casting, export
│   │   └── websocket/          # Socket.IO events (Redis emitter)
│   ├── prompts/                # 17 prompt templates
│   ├── migrations/             # Alembic (13 revisions)
│   └── tests/                  # 311 unit tests
├── frontend/                   # Next.js 14 + TypeScript + Tailwind
│   └── app/projects/[id]/      # Script → Characters → Storyboard → Generate → Export
├── docker-compose.yml          # api + worker + frontend + postgres + redis + neo4j
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, Tailwind, Zustand, React Query, D3 force graphs, Socket.IO, Monaco |
| Backend | FastAPI, LangGraph, SQLAlchemy 2.0, Alembic, Celery, Redis, Socket.IO |
| AI | qwen-max / plus / flash, qwen3-vl-plus, Wan 2.7, HappyHorse 1.1, qwen3-tts (+ voice cloning), insightface ArcFace |
| Infrastructure | Alibaba Cloud OSS, PostgreSQL + pgvector, Redis, Neo4j, FFmpeg |

---

## Highlights

- **Self-correcting agent** — the judge's critique feeds the rewrite; weak hooks and flat endings never reach generation
- **Budget fitting, not budget reporting** — hook protection, tier downgrades, deferrals; the plan always fits the user's cap
- **Provable consistency** — a production bible conditions every clip, and each clip shows the exact references it used
- **A finished product** — one premise becomes a watchable 9:16 episode with placed dialogue, ducked music, and burned-in subtitles
- **The engineering is on screen** — live token dashboard, agent activity feed, story map, beat sheet, per-clip provenance
- **311 unit tests**, CI against Postgres, 13 migrations, graceful degradation on every external dependency

---

## License

[MIT](LICENSE)
