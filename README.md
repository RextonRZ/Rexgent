# Rexgent

> Give me a story idea. I'll hand you back a finished episode — or a whole season — vertical or widescreen.

Rexgent is an **autonomous AI showrunner** built on **Qwen Cloud**. Type a one-line premise and an agent runs the whole production: script, self-critique and revision, casting, storyboarding with camera-executable blocking, budget allocation, video generation, dialogue, and a final cut per episode — while a live dashboard shows every token and cent it spends.

Underneath the pipeline sit the two systems this README is really about: a **layered anti-hallucination defense** that treats video-model failure modes as engineering problems (not prompt luck), and a **continuity engine** that makes the same face, outfit, room and screen-side geometry survive across every cut — with **Neo4j holding both the story's memory and the world's physics**.

**Built for:** [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 2: AI Showrunner

---

## What a run looks like

1. Create a drama: premise + genre + episode count + format (9:16 vertical or 16:9 widescreen) + a **spend cap** — a live panel projects the tokens and dollars this drama will cost before anything runs
2. Flip **Full Auto** and watch the agent: write → judge (8 axes incl. hook strength) → revise with the judge's own critique → extract characters → storyboard
3. The **beat sheet** shows the ladder: logline → scene beats, with the 3-second hook and per-episode cliffhangers tagged
4. Casting builds the **production bible**: identity plates, per-outfit costume plates, location plates, one style plate — and a **voice designed for each character** from their age, gender and personality (a 17-year-old bully stops sharing a preset with a mid-40s mother), with free presets as fallback and 10-second cloning as an upgrade
5. The **set dresser** pins each scene's props — and tracks state ("from shot 3: the vase lies shattered")
6. The **storyboard carries camera-executable geometry**: every shot's blocking (who stands where, facing whom, in what posture) renders as an interactive top-down camera plan, and the 180° rule is enforced deterministically — not requested politely
7. Budget allocation **fits the plan to the cap**: hook shots protected on Wan 2.7, supporting shots downgraded to HappyHorse, the least important deferred — and when the cap is too small, the agent names the exact cap that fits and offers a one-click raise
8. Generation runs live: every clip shows its **reference provenance**, its continuity score from real ArcFace embeddings, and a **prompt engineering panel** — the exact positive prompt, the negative prompt, and which world-graph rule shaped the environment
9. The **crew workflow graph** shows the machinery live: every stage expands into its real tools — model calls, DB writes, validators — ticking one by one
10. Export cuts each episode: dialogue placed on the exact shots that speak it — **entering the moment the on-screen mouth starts moving** — music ducking under speech, captions burned in, held endings with fades, one video per episode plus a zip of the season
11. **Usage & Analytics** proves the routing thesis across every drama: share of language work on cheap tiers, dollars saved vs all-premium, per-model receipts, continuity + retry reliability, and an interactive budget-runway planner

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
    C -- clear --> SB[storyboard<br/>blocking + set dresser]
    SB --> CAST[casting:<br/>bible plates + voices]
    CAST --> AUD[dialogue TTS]
    AUD --> B[budget: fit plan<br/>to spend cap]
    B --> V[generate video<br/>per-shot references]
    V --> E[auto export:<br/>per-episode cuts + subtitles]
    E --> DONE((episodes))
```

Plan-only by default (nothing is spent until you approve); **Full Auto** runs the whole graph and the finished episode renders itself the moment the last clip lands.

---

## Fighting Hallucination — a layered defense

Video models don't fail randomly. They fail in *predictable* ways: they fill underspecified prompts with safe priors, they can't render a state change inside one clip, they sanitize violence into hugs, they apply a location's default mood even when the story just broke it, and they paint one reference face onto two bodies. Rexgent treats each failure mode as a named engineering problem with a named defense:

| Failure mode | What it looked like | The defense |
|---|---|---|
| **Safe-prior filling** | "Performer collapses on stage" rendered the audience standing and applauding | **Concrete action expansion**: the prompt crafter must translate every beat into observable physical action — body, hands, face, props — with vague intensity words ("dramatic", "shocking", "intense") banned outright |
| **Wrong default suppressed too late** | Negatives were generated but silently discarded before dispatch | **Beat-targeted negative prompts** ride `input.negative_prompt` into both Wan and HappyHorse (with a schema-rejection fallback so an unsupported model degrades gracefully): a collapse at a concert explicitly negates "applause, clapping, cheering, smiling audience" |
| **State changes inside one clip** | A 5-second clip cannot show before → during → after; the model picks one state and improvises the rest | **Event decomposition at boarding**: a collapse/attack/death/crash beat becomes 2-3 consecutive *single-state* shots (baseline · during · aftermath), each opening already inside its state — the words "suddenly" and "begins to" are banned from a shot's action |
| **Violence sanitized into nothing** | A murder rendered as an awkward hug | **Violence by implication**: the storyboard never boards the act — it boards the raised weapon, the victim's face, the slumped aftermath. The cut IS the violence. (This is also how real film does it) |
| **Location default overrides the event** | The concert crowd cheered *in the very shot* the performer collapses | **The environment-reaction graph in Neo4j** (see below): the event's behavior override outranks the location default by priority, the winner is injected into the positive prompt, and the suppressed default lands in the negative |
| **Faces re-invented on props** | Footage "shown on a phone" rendered the on-screen character as a second physical person, face-bled from the watcher's references | **Device-screen rule**: a character who exists only inside a phone/TV/photo is never listed in the cast or blocking; the screen renders as an unreadable glow and the content reaches the audience through reaction + audio. Plus a **mandatory anti-duplicate negative** ("duplicate person, cloned face, same face on two people") on every render |
| **Text hallucination** | Garbled captions, signs, watermarks inside footage | `PromptSanitizer` strips quotes/names/numbers from prompts and injects anti-text negatives on every single render |
| **Name-variant identity loss** | The storyboard wrote "KERRY (ON SCREEN)" and every exact-match consumer — validator, reference stacks, continuity — lost her | **Canonical character resolution**: stage qualifiers ("(ON SCREEN)", "(V.O.)") resolve back to the cast member at boarding, in the validator, and in the blocking |
| **LLM schema drift** | Blocking subjects arrived as bare names, flattened key:value strings, and even JSON-objects-as-strings | A **drift normalizer** un-mangles all three observed shapes (with tests locking each), and the diagram renders nothing rather than render a lie when geometry is truly absent |

And the transformation is **visible evidence**, not backend folklore: every rendered shot card carries a *prompt engineering* disclosure showing the original beat, the exact prompt sent to the video model, the negative prompt, and the environment resolution in plain words ("the event performer_collapse (priority 10) overrides the concert hall default...").

---

## The Continuity Engine

The #1 quality problem in AI video is drift — faces, outfits, rooms and screen geography that change between shots. Rexgent attacks it on four axes, and makes each one **provable**:

**Identity.**
- Identity plates + per-outfit **costume plates** (image-edited *from* the same face so identity survives wardrobe changes), location plates, one style plate per drama
- **Reference stacks** per shot in a deliberate order: identity → scene costume → previous-shot frame → scene anchor frame → location (wide shots only) → style
- Identity plates are **verified at birth**: candidate plates are embedded with ArcFace and cosine-scored against the user's reference photo (best-of-2), so a bad plate never enters the bible
- **Deterministic seeds** per shot — re-renders differ only by what you changed, never by RNG luck

**Geometry.**
- Every shot carries **absolute blocking**: each character's frame depth (FG/MG/BG), screen side, facing, eyeline, and **posture** (a character lying unconscious in a hospital bed renders as lying, not as an upright pin)
- The **180° rule is enforced deterministically** by a stage map: a character's first left/right placement establishes their side, later drift is snapped back in the data itself, and only a deliberate `reverse_angle` re-establishes the line
- **React-then-reveal** and **dialogue coverage** rules stage entrances and spoken lines the way editors actually cut them — reaction first, reveal second, mouths hidden unless a shot is genuinely lip-driven
- The blocking renders as an **interactive top-down camera plan**: depth-scaled tokens on a stage, facing wedges, dashed eyelines between characters who look at each other, and a camera whose position and cone follow the shot type (an OTS shoots from behind the foreground shoulder; a close-up narrows to a sliver)

**World state.**
- **Set dresser**: per scene, the props every shot must render identically — with **prop state tracking** (a vase broken in shot 3 stays broken in shot 4; the pristine location plate is dropped once the state changes)
- **Frame chaining**: each clip's true final frame is extracted and stored; Wan shots continue from the previous shot's last frame, the first wide shot's closing frame anchors the whole scene's room, and resume runs re-seed the chain from already-approved shots' stored frames

**Verification.**
- **Continuity scoring** after every clip: real ArcFace embeddings (insightface) + a Qwen-VL outfit/background check; weak clips are flagged `NEEDS_REVIEW`, never silently shipped
- **Resume-skip re-rendering**: reject a bad take and press generate — approved shots skip at zero cost, only the rejected shot re-renders (with the full anchor chain intact)
- **Provenance on screen**: every clip tile shows the exact reference images that conditioned it

---

## Neo4j — the story's memory and the world's physics

Rexgent runs **two knowledge graphs** on one Neo4j instance, and the agent both writes and reads them:

**1. Narrative memory.** As scenes are dressed and staged, facts land in the graph — `(Character)-[:KNOWS_ABOUT]->(Fact)-[:ESTABLISHED_IN]->(Scene)`, with `CONTRADICTS` edges and typed `RELATES_TO` relationships between characters. Before staging every scene, the Director queries *everything the story established earlier* so later shots can't contradict canon. The same graph powers the story map UI: a force graph of who appears in which scene, filtered per episode.

**2. The environment-reaction graph** — world knowledge as data, not code:

```cypher
(Location)-[:DEFAULT_BEHAVIOR {priority: 0}]->(EnvironmentBehavior)
(Event)-[:OVERRIDES {priority: N}]->(EnvironmentBehavior)
```

A concert hall's default is a cheering crowd. But when the shot's action contains a `performer_collapse` event (keyword-detected — zero LLM tokens), the resolver query picks the **highest-priority applicable behavior**: the crowd freezes in shock (priority 10 beats 0). The winning behavior is injected into the positive prompt; the *suppressed* default is injected verbatim into the negative prompt — so the model is simultaneously told what the room does now and forbidden from doing what it does by default. Ten locations, a dozen events, and a set of behaviors ship as seed data; **extending the world is a MERGE, not a code change**. If Neo4j is down, the pipeline degrades to exactly its old behavior — the graph is an enhancement, never a gate.

---

## The Audio Brain

Rexgent's audio pipeline is **audio-first**: dialogue is synthesized and measured *before* video renders, and the pictures are fitted to the sound.

- **Voices are cast, not picked from a menu.** `qwen-voice-design` writes a bespoke voice from each character's sheet — age, gender, personality — and `qwen3-tts-vd` speaks every line with it. Presets remain the free fallback (and keep per-line delivery directions via `qwen3-tts-instruct-flash`, which turns stage directions like "(whispering, frantic)" into acted delivery); cloning from a 10-second sample rides `qwen3-tts-vc-realtime`. The casting page shows the exact design each voice was built from
- **Shot durations follow the lines**: every speaking shot is sized to the real length of its synthesized audio, so two-person exchanges never talk over each other. Stage directions are stripped from the spoken text — they're *acted*, not read aloud
- **The k-th line convention**: scene line k belongs to the scene's k-th speaking shot — one convention shared by placement, lip-sync and export, so mouth and overlay can't disagree. A global no-overlap sweep guards collisions
- **Keep the model's own soundtrack — intelligently.** A generated clip's audio is one mixed track: music + ambience + sometimes hallucinated speech. A local VAD answers first (free); when it cries "speech" — it scores real film scores 0.98+ "voiced", a known music bias — **qwen3-asr-flash gets the final say**: a track that transcribes to ≤2 words is music and survives as a bed under the voices; real fake dialogue gets muted. The verdict is computed **once per clip and stored**, so the editor preview and the export can never disagree
- **The voice enters when the mouth moves.** `fun-asr-realtime` sentence timestamps locate when each clip's fake speech actually starts; the real TTS line is placed at *chunk start + onset* instead of at the hard cut — measured live: "I can't do this anymore" enters at 2.17s, exactly where the character's mouth starts
- **True lip-sync where the model allows it**: eligible Wan shots render with `driving_audio` — the line's own TTS drives the mouth — behind strict eligibility rules (sole visible speaker, first attempt, duration fits) and a graceful fallback chain (lip-sync → plain continuation → HappyHorse r2v). Every other spoken line gets mouth-hiding coverage so an unsynced flapping mouth is never front-and-center
- **Endings land instead of stopping**: if the final voice line outruns the footage, the last frame holds until it finishes, then picture and sound fade out together. (And a hard-won fix: model clips' audio runs ~0.3s short of their video, so a naïve `-shortest` mix chopped seconds off every episode — measured, root-caused, removed)

---

## Preview = Export, by construction

The editor's preview isn't a hopeful approximation — it shares the export's actual algorithms:

- A `preview_plan` endpoint runs the **export worker's own placement math** (cut plan + dialogue placement, pure math, no ffmpeg) on the current timeline in milliseconds
- The player overlays each caption at its placed time, styled like the burned one, and **plays the real TTS voices in sync**, with clip audio obeying the same stored mute/bed verdicts the export uses
- A **CapCut-style caption lane** inside the timeline shows every line under the exact clip it plays over, reflowing live on trims and reorders
- Once an export exists, an **Editor preview / Final render** toggle plays the true shipped file — burned captions, full mix, fades
- Trims are exported only when the user actually trimmed (a placeholder-trim bug that silently halved 10-second clips was found by running ASR *on the shipped file* and comparing measured line positions against the placement math — the kind of verification this pipeline is built for)

---

## Multi-episode delivery

Episodes aren't a label — they're a delivery format:

- The screenwriter writes N episode arcs, each ending on a cliffhanger; the structurer records each scene's episode
- The storyboard groups scenes under episode headers; the story map and scene flow filter per episode; the generation queue badges every scene
- The export editor cuts **one episode at a time** (tabs rebuild the timeline per episode), or **Export all episodes** renders every episode in one run — each as its own captioned, mixed `final_ep{n}.mp4` — with a **Download all (.zip)** of the season
- A one-episode drama shows none of this chrome and behaves exactly as before

---

## Maximizing Quality Under a Token Budget

The track's core constraint, treated as an engineering problem:

| Lever | How Rexgent does it |
|-------|--------------------|
| **Model tiering** | A `ModelRouter` sends each task to the cheapest capable Qwen tier: **qwen-max only writes** (script, storyboard), **qwen-plus judges** (narrative judge, plot gaps, prompt craft), **qwen-flash does deterministic work** (structuring, extraction, wardrobe, set dressing, titles) |
| **Attribution** | Every LLM call lands on the drama's cost ledger with its model and task — spend per stage, per tier, live |
| **Structured output** | Native JSON mode with graceful fallback + array unwrapping; truncation retry; trailing-comma repair |
| **Context compression** | Non-creative agents receive a scene digest, not the full script JSON |
| **Adaptive allocation** | `TokenOptimizer` scores every shot's narrative importance, protects the hook on Wan 2.7, and **fits the plan to the user's spend cap**: downgrade least-important Wan shots to HappyHorse, then defer what still doesn't fit |
| **Honest shortfalls** | An undersized cap doesn't silently amputate scenes: the allocator computes the smallest cap that renders the full plan and the UI offers a one-click "Set budget to $N" |
| **Priced consent** | Every paid button opens an **itemized receipt** naming each model, its unit price and a live total before anything runs — "Start generation" prices the Producer's *actual fitted plan* on click (premium × N on Wan 2.7, standard × M on HappyHorse, deferred at $0.00), and optional spends like a designed voice are tickable line items |
| **Zero-token world knowledge** | Environment events are keyword-detected and resolved by a Cypher query — the world graph costs no LLM tokens at all |
| **Cached verdicts** | Per-clip audio policies (VAD + ASR) and speech onsets are measured once and stored — never re-billed at preview or export time |
| **Re-render economy** | Deterministic seeds + resume-skip: fixing one bad shot costs one shot |
| **Visible** | A live token dashboard: tokens vs cap, per-model tier chips, cheap-tier share, per-stage bars |

---

## Architecture

```mermaid
flowchart TB
    subgraph FE[Frontend — Next.js 14]
        UI[Script · Characters · Storyboard · Generate · Export]
        TD[Live token + cost dashboard]
        SM[Story map · Camera plans · Beat sheet · Bible panels]
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
        GEN[generation runner<br/>reference stacks · seeds · continuity · lip-sync]
        CASTW[casting worker<br/>bible plates · voices]
        EXP[export worker<br/>ffmpeg: stitch · onset-placed voices · duck · captions · per-episode]
    end
    API -- "dispatch jobs<br/>(Redis broker)" --> WK

    subgraph QWEN[Qwen Cloud / DashScope intl]
        LLM[qwen-max · qwen-plus · qwen-flash]
        VID[wan2.7 t2v/i2v + driving_audio · happyhorse-1.1 t2v/i2v/r2v]
        IMG[wan2.6-t2i · qwen-image-edit-max]
        VL[qwen3-vl-plus] & TTS[qwen3-tts-vd · voice design · cloning]
        ASR[qwen3-asr-flash · fun-asr-realtime]
    end
    TOOLS -- "task-routed: max writes,<br/>plus judges, flash structures" --> LLM
    WK --> QWEN

    subgraph INFRA[Infrastructure]
        PG2[(PostgreSQL + pgvector<br/>512-d face vectors)] & RD[(Redis)] & OSS[(Alibaba OSS<br/>plates · clips · voices · exports)] & N4J[(Neo4j<br/>narrative memory +<br/>environment-reaction graph)]
    end
    API --> INFRA
    WK --> INFRA
    WK -- "stage / tool / ledger events" --> RD
    RD -- "Socket.IO fan-out: dock, crew<br/>graph, cost meter update live" --> FE
```

---

## Qwen Cloud Integration — 17 models, routed by task

| Component | Qwen Model | Purpose |
|-----------|-----------|---------|
| Script + storyboard writing | Qwen-Max | The only creative-writing tier |
| Judging, plot gaps, endings, prompt craft | Qwen-Plus | Analysis at a third of the cost |
| Structuring, extraction, wardrobe, set dressing, titles | Qwen-Flash | Deterministic JSON work, ~15x cheaper output |
| Hero + hook shots, lip-sync | Wan 2.7 (t2v/i2v + driving_audio) | Premium 1080P, native 9:16/16:9, seeded, mouth driven by the line's own TTS |
| Supporting shots | HappyHorse 1.1 (t2v/i2v/r2v) | Reference-to-video with up to 9 reference images |
| Clip surgery (regen loop) | HappyHorse 1.0 video-edit | Video-to-video fixes from user flags |
| Bible plates | wan2.6-t2i + qwen-image-edit-max | Costume plates edited FROM the face so identity carries |
| Continuity vision check | qwen3-vl-plus | Outfit + background scoring per clip |
| Reference photo analysis | qwen-vl-max | Reads uploaded photos for casting + outfit swap |
| Voice casting | qwen-voice-design + qwen3-tts-vd | Casting **writes a bespoke voice** from each character's age and personality — a 17-year-old bully and a mid-40s mother stop sharing the same six presets |
| Dialogue | qwen3-tts-vd (designed) with qwen3-tts-flash + instruct-flash fallback, voice enrollment + vc-realtime cloning | Every line in the character's own designed voice; presets honor per-line delivery instructions via instruct-flash; or clone from a sample (realtime WS) |
| Soundtrack triage | qwen3-asr-flash | Transcribes clip audio: wordless = music worth keeping, words = fake speech to mute |
| Audio-visual alignment | fun-asr-realtime | Sentence timestamps locate when the on-screen mouth starts — the voice is placed there |

### 7 Custom Tools — one registry, two transports

Served identically over FastAPI HTTP **and** a real MCP stdio server (official `mcp` SDK), from one shared registry ([`backend/app/mcp_tools/registry.py`](backend/app/mcp_tools/registry.py)):

| Tool | Innovation |
|------|-----------|
| `NarrativeJudge` | LLM-as-critic on 8 axes including **hook_strength** and **cliffhanger_pull** — a weak opening blocks generation and drives the revision loop |
| `TokenOptimizer` | Budget fitting, not budget reporting: hook protection, tier downgrades, deferrals, and a computed "smallest cap that fits" recommendation |
| `SetDresser` | Persistent set dressing + prop **state** tracking per scene (a broken vase stays broken) |
| `ScenePromptCraft` | Cinematic prompt DSL: concrete-action expansion, single-state clips, violence-by-implication, blocking injection, environment-reaction injection, beat-targeted negatives, anti-text sanitization, DoF-by-framing |
| `ConsistencyGuard` | Face verification via real ArcFace embeddings with VLM diagnosis |
| `PlotGapDetector` | Typed narrative problem detection — like linting for scripts |
| `EndingEngine` | Ending completeness + branching alternatives |

### AI Guardrails

| Guardrail | What It Prevents |
|-----------|-----------------|
| `PromptSanitizer` | Text/number hallucination — strips quotes, scene numbers, names; injects anti-text **and anti-duplicate-person** negatives on every render |
| `canonical_character` | Identity loss from name variants — "KERRY (ON SCREEN)" resolves to KERRY everywhere names are matched |
| Blocking drift normalizer | LLM schema drift — un-mangles bare-name, flattened-string and JSON-as-string subject shapes (each locked by tests) |
| `CostCircuitBreaker` | Budget overrun — hard stop at 85% of the drama's own spend cap |
| `InputSanitizer` | Prompt injection in user inputs |
| `PreGenerationValidator` | Missing character visuals, empty storyboards — blocks before spending (variant-name tolerant) |
| Continuity review queue | Weak clips flagged `NEEDS_REVIEW`, never silently shipped (and never retry-spammed) |
| Stage map | 180° line violations — snapped back in the data, deterministically |

---

## Getting Started

### Prerequisites

- Python 3.11+ · Node.js 20+ · Docker & Docker Compose
- [Qwen Cloud](https://www.qwencloud.com/) API key (international / dashscope-intl)
- Alibaba Cloud OSS bucket

### Quick Start (Docker)

```bash
git clone https://github.com/RextonRZ/Rexgent.git
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
git clone https://github.com/RextonRZ/Rexgent.git && cd Rexgent
# copy your backend/.env onto the server (scp) — never commit it

export PUBLIC_API_URL="http://<server-ip>:8000"      # baked into the frontend build
export FRONTEND_ORIGIN="http://<server-ip>:3000"     # added to CORS (HTTP + websocket)
docker compose -f docker-compose.yml up -d --build
```

Migrations run automatically on backend start. Open `http://<server-ip>:3000`.
With a domain, put Caddy or Nginx in front for HTTPS and set both URLs to the
https origin instead.

What runs where — one ECS instance hosts the whole stack; media and models
stay on managed Alibaba services:

```mermaid
flowchart LR
    U([Browser])
    subgraph ECS["Alibaba Cloud ECS — docker compose"]
        FE2["frontend :3000<br/>Next.js standalone"]
        BE["backend :8000<br/>FastAPI + Socket.IO + Alembic"]
        WK2["worker<br/>Celery ×2 + ffmpeg"]
        RD2[("Redis 7<br/>broker + event bus")]
        DB[("PostgreSQL 16<br/>pgvector")]
        N4[("Neo4j 5")]
    end
    DS["Qwen Cloud<br/>DashScope intl — 17 models"]
    OSS2[("Alibaba OSS<br/>plates · clips · voices · final_ep{n}.mp4")]

    U --> FE2
    U -- "REST + WebSocket" --> BE
    BE <--> RD2
    RD2 <--> WK2
    BE --> DB & N4
    WK2 --> DB
    BE -- "LLM / VL calls" --> DS
    WK2 -- "video · image · TTS · ASR" --> DS
    WK2 -- "persist media" --> OSS2
    U -. "signed media URLs" .-> OSS2
```

> **Submission note:** after `docker compose up`, capture the ECS console
> screenshot (instance page showing the running host) plus `docker compose ps`
> output — Devpost requires the deployment verification image.

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
│   │   ├── graph/              # Neo4j: narrative memory + environment-reaction graph
│   │   ├── models/             # 19 ORM models (bible, clips, cost events, ...)
│   │   ├── routers/            # API endpoints per stage
│   │   ├── services/           # model router · reference stacks · stage map · set dresser ·
│   │   │                       # generation runner · lipsync · audio policy · stitcher ·
│   │   │                       # cost ledger · guardrails
│   │   ├── mcp_tools/          # 7 shared tools (HTTP + MCP)
│   │   ├── mcp_server/         # real MCP stdio server (official SDK)
│   │   ├── workers/            # Celery: generation, casting, storyboard, export
│   │   └── websocket/          # Socket.IO events (Redis emitter)
│   ├── prompts/                # 17 prompt templates
│   ├── migrations/             # Alembic (21 revisions)
│   └── tests/                  # 472 unit tests
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
| AI | qwen-max / plus / flash, qwen3-vl-plus, Wan 2.7 (+driving_audio), HappyHorse 1.1, qwen3-tts (+ voice cloning), qwen3-asr-flash, fun-asr-realtime, insightface ArcFace, webrtcvad |
| Infrastructure | Alibaba Cloud OSS, PostgreSQL + pgvector, Redis, Neo4j, FFmpeg |

---

## Highlights

- **Self-correcting agent** — the judge's critique feeds the rewrite; weak hooks and flat endings never reach generation
- **Hallucination as an engineering problem** — nine named failure modes, nine named defenses, and the receipts visible on every shot card
- **Budget fitting, not budget reporting** — hook protection, tier downgrades, deferrals, and a computed "this cap fits" recommendation
- **Audio-first cutting with audio-visual alignment** — dialogue synthesized and measured BEFORE video renders, and each voice enters the moment its on-screen mouth starts moving (ASR sentence timestamps)
- **Voices designed per character** — qwen-voice-design writes each voice from the character's age and personality, qwen3-tts-vd speaks it, and the casting page shows the design; presets and 10-second cloning remain as free fallback and upgrade
- **Two Neo4j graphs** — narrative memory the Director reads back before staging, and a priority-weighted environment-reaction graph where events override location defaults as pure data
- **Preview = export by construction** — one placement algorithm, one stored audio verdict per clip, and a final-render toggle to audit the shipped file
- **Multi-episode delivery** — cliffhanger-structured writing to per-episode cuts and a season zip
- **Glass-box orchestration** — a live two-level crew graph (stages → tools), per-clip provenance and prompt-engineering panels, and a Usage & Analytics page with per-model receipts
- **472 unit tests**, CI against Postgres, 21 migrations, graceful degradation on every external dependency

---

## License

[MIT](LICENSE)
