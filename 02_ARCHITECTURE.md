# ShowMind — System Architecture

**Version:** 1.0  
**Stack:** Next.js 14 · FastAPI · Alibaba Cloud · Qwen Cloud APIs

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│              Next.js 14 (App Router) + React                 │
│   Script Editor │ Character Engine │ Storyboard │ Editor     │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS / WebSocket
┌──────────────────────▼──────────────────────────────────────┐
│                   API Gateway (FastAPI)                       │
│              Deployed on Alibaba Cloud ECS                   │
│  /script  /characters  /storyboard  /generate  /edit  /ws   │
└──────────┬───────────────────────────────────┬──────────────┘
           │                                   │
┌──────────▼───────────┐         ┌─────────────▼──────────────┐
│   Orchestrator       │         │    MCP Tool Server          │
│   (Qwen-Max)         │         │    (FastAPI microservice)   │
│   Narrative Memory   │         │  ScenePromptCraft           │
│   Graph              │         │  ConsistencyGuard           │
│                      │         │  TokenOptimizer             │
│                      │         │  NarrativeJudge             │
│                      │         │  PlotGapDetector            │
│                      │         │  EndingEngine               │
└──────────┬───────────┘         └─────────────┬──────────────┘
           │                                   │
┌──────────▼───────────────────────────────────▼──────────────┐
│                   Qwen Cloud APIs                            │
│   Qwen-Max │ Qwen-VL │ Wan 2.7 │ HappyHorse 1.1 │ Qwen-TTS  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                 Alibaba Cloud Storage                         │
│   OSS (videos, images, exports) │ Redis (session/queue)      │
│   PostgreSQL via RDS (projects, characters, scripts)         │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Frontend Architecture

### Tech Stack
- **Framework:** Next.js 14 with App Router
- **UI:** React 18 + Tailwind CSS + shadcn/ui
- **State:** Zustand (global project state) + React Query (server state)
- **Graph rendering:** D3.js (relationship graph, scene graph)
- **Video player / editor:** custom React component wrapping native `<video>` + FFmpeg.wasm for client-side trim
- **Real-time:** WebSocket via `socket.io-client` (generation progress)
- **File upload:** `react-dropzone` for PDF / Word / image uploads

### Page Structure

```
/app
  /(auth)
    /login
    /register
  /(workspace)
    /projects                        → project list
    /projects/[id]
      /script                        → script editor + analysis
      /characters                    → character engine
      /storyboard                    → storyboard + budget
      /generate                      → generation dashboard
      /edit                          → video editor
      /export                        → final render + download
  /api
    /upload                          → presigned URL handler
    /ws                              → WebSocket upgrade
```

### Key Frontend Components

```
components/
  script/
    ScriptEditor.tsx                 → Monaco-based script editor
    PlotGapPanel.tsx                 → inline flag annotations
    EndingGraph.tsx                  → D3 branching ending graph
  characters/
    CharacterCard.tsx                → full character profile card
    FaceUpload.tsx                   → drag-drop image upload + preview
    RelationshipGraph.tsx            → D3 force-directed graph
    SceneGraph.tsx                   → D3 scene dependency graph
    MBTIBadge.tsx                    → MBTI display with confidence
  storyboard/
    StoryboardCard.tsx               → individual shot card
    ShotEditor.tsx                   → editable shot fields
    BudgetDashboard.tsx              → token budget UI
    QualityTierPicker.tsx            → drag scenes between tiers
  generate/
    GenerationQueue.tsx              → real-time clip progress
    ConsistencyBadge.tsx             → pass/fail/retry status per clip
  edit/
    Timeline.tsx                     → horizontal clip timeline
    ClipViewer.tsx                   → video player with trim handles
    FlagPanel.tsx                    → change instruction form
    RegenComparison.tsx              → A/B clip comparison
  shared/
    TokenBudgetBar.tsx               → always-visible budget indicator
    QwenModelBadge.tsx               → shows which model processed this
```

---

## 3. Backend Architecture

### Tech Stack
- **Framework:** FastAPI (Python 3.11)
- **Task queue:** Celery + Redis (for async video generation jobs)
- **Database:** PostgreSQL (via SQLAlchemy ORM)
- **ORM models:** Project, Script, Scene, Character, Shot, GeneratedClip, EditFlag
- **File storage:** Alibaba Cloud OSS SDK (oss2)
- **Video processing:** FFmpeg (subprocess) for stitching + caption burning
- **Deployment:** Alibaba Cloud ECS (2× vCPU, 8GB RAM) + auto-scaling

### API Routes

```
POST   /api/script/parse              → parse uploaded PDF/Word file
POST   /api/script/generate           → generate script from premise
POST   /api/script/analyze            → run plot gap detector + ending engine
GET    /api/script/{id}               → get structured script

POST   /api/characters/extract        → auto-extract from script
POST   /api/characters/create         → manual character creation
POST   /api/characters/{id}/face      → upload + embed reference image
POST   /api/characters/{id}/generate  → AI generate appearance
GET    /api/characters/{id}           → get character profile

POST   /api/graph/relationship        → build relationship graph
POST   /api/graph/scene               → build scene dependency graph
GET    /api/graph/{script_id}         → get both graphs

POST   /api/storyboard/generate       → auto-generate storyboard
PATCH  /api/storyboard/{shot_id}      → edit individual shot
POST   /api/budget/calculate          → recalculate token budget

POST   /api/generate/start            → start full generation run
GET    /api/generate/{job_id}/status  → poll job status
GET    /api/generate/{job_id}/clips   → get completed clips

POST   /api/edit/trim                 → define trim points on clip
POST   /api/edit/flag                 → submit change flag
POST   /api/edit/regen                → regenerate flagged clip
POST   /api/edit/approve              → approve clip for final assembly

POST   /api/export/render             → trigger final FFmpeg render
GET    /api/export/{job_id}/download  → get presigned OSS download URL

WS     /ws/{project_id}               → real-time generation progress events
```

### Database Schema (simplified)

```sql
Project         (id, user_id, title, genre, status, created_at)
Script          (id, project_id, raw_text, structured_json, version)
Character       (id, project_id, name, role, description, mbti, face_embedding, reference_image_url)
CharacterRel    (id, project_id, from_char_id, to_char_id, rel_type, strength, evidence_scene_id)
Scene           (id, script_id, number, title, location, time_of_day, characters_json, description)
Shot            (id, scene_id, number, shot_type, camera_movement, lighting, colour_mood, action, duration, quality_tier)
PlotFlag        (id, script_id, scene_id, flag_type, description, suggestion, status)
GenerationJob   (id, project_id, status, total_shots, completed_shots, estimated_cost, actual_cost)
GeneratedClip   (id, job_id, shot_id, model_used, url, consistency_score, status, retries)
EditFlag        (id, clip_id, flag_type, description, direction, status)
FinalExport     (id, project_id, url, duration_seconds, created_at)
```

---

## 4. Orchestrator Design

The Master Orchestrator is a Python class that wraps all Qwen-Max calls and maintains the Narrative Memory Graph across the session.

```python
class ShowMindOrchestrator:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.memory_graph = NarrativeMemoryGraph()
        self.client = QwenClient(model="qwen-max")
    
    # Each method reads from and writes to self.memory_graph
    async def parse_script(self, raw_text: str) -> StructuredScript
    async def detect_plot_gaps(self, script: StructuredScript) -> list[PlotFlag]
    async def detect_ending(self, script: StructuredScript) -> EndingAnalysis
    async def extract_characters(self, script: StructuredScript) -> list[Character]
    async def infer_mbti(self, character: Character) -> MBTIResult
    async def build_relationship_graph(self, characters: list, script: StructuredScript) -> RelGraph
    async def generate_storyboard(self, script: StructuredScript) -> list[Shot]
    async def score_scenes(self, shots: list[Shot]) -> list[ScoredShot]
    async def craft_prompt(self, shot: Shot, characters: list[Character]) -> str
    async def judge_script(self, script: StructuredScript) -> NarrativeJudgement
    async def rewrite_prompt(self, original: str, flag: EditFlag) -> str
```

### Narrative Memory Graph

```python
@dataclass
class NarrativeMemoryGraph:
    # Characters
    characters: dict[str, CharacterState]      # name → current state
    
    # Established facts (prevent contradictions)
    facts: list[NarrativeFact]                  # scene_id, fact_text, category
    
    # Visual motifs (ensure visual consistency)
    motifs: list[VisualMotif]                   # motif_name, description, scenes
    
    # Tension curve (track pacing)
    tension_curve: list[TensionPoint]           # scene_id, score (0–10)
    
    # Generated prompt history (reference for consistency)
    prompt_history: list[PromptRecord]          # shot_id, prompt, output_url
    
    def get_character_context(self, character_name: str, scene_id: str) -> str:
        """Returns character state at a specific scene for prompt injection"""
    
    def get_established_facts(self, scene_id: str) -> list[str]:
        """Returns all facts established before this scene"""
    
    def check_contradiction(self, new_fact: str, scene_id: str) -> bool:
        """Returns True if new_fact contradicts existing graph"""
```

---

## 5. MCP Tool Server

All 6 custom tools are served as a separate FastAPI microservice, callable by the Orchestrator.

```python
# ScenePromptCraft
@tool("scene_prompt_craft")
async def build_cinematic_prompt(
    shot: Shot,
    characters_in_frame: list[Character],
    narrative_context: str,
    style_bible: dict
) -> str:
    """
    Builds an optimised cinematic prompt for Wan/HappyHorse.
    Never uses character names — only visual descriptions.
    Injects face description keywords from character bible.
    """

# ConsistencyGuard  
@tool("consistency_guard")
async def validate_frame_consistency(
    clip_url: str,
    expected_characters: list[Character],
    sample_frames: int = 3
) -> ConsistencyResult:
    """
    Downloads clip, samples N frames, calls Qwen-VL on each.
    Compares face embeddings against character bible.
    Returns overall pass/fail + per-character similarity scores.
    """

# TokenOptimizer
@tool("token_optimizer")
async def score_and_allocate(
    shots: list[Shot],
    budget_usd: float,
    wan_cost_per_sec: float = 0.07,
    hh_cost_per_sec: float = 0.05
) -> list[ScoredShot]:
    """
    Scores each shot by emotional weight.
    Allocates quality tiers to maximise quality within budget.
    Returns cost forecast + tier assignment per shot.
    """

# NarrativeJudge
@tool("narrative_judge")  
async def judge_script(script: StructuredScript) -> NarrativeJudgement:
    """
    Second Qwen-Max call (acting as critic, not author).
    Rates script on: tension arc, character consistency,
    pacing, dialogue naturalness, genre adherence.
    Returns score + blocking issues before any generation begins.
    """

# PlotGapDetector
@tool("plot_gap_detector")
async def detect_gaps(script: StructuredScript) -> list[PlotFlag]:
    """
    Reads full script and returns typed flags.
    Flag types: MISSING_MOTIVATION, CONTINUITY_BREAK,
    UNRESOLVED_THREAD, PACING_ISSUE.
    Each flag includes scene number, line ref, suggestion.
    """

# EndingEngine
@tool("ending_engine")
async def analyse_ending(script: StructuredScript) -> EndingAnalysis:
    """
    Checks final act for resolution completeness.
    If incomplete: generates 3 branching ending options.
    Returns ending graph with compatibility scores.
    """
```

---

## 6. Video Generation Pipeline

### Generation Job Flow

```
1. GenerationJob created (status: PENDING)
2. Celery worker picks up job
3. For each shot in storyboard:
   a. ScenePromptCraft builds prompt
   b. TokenOptimizer determines model (Wan or HappyHorse)
   c. API call dispatched (async)
   d. Polling loop waits for completion
   e. On completion:
      - Clip downloaded to temp storage
      - ConsistencyGuard validates frames
      - If pass: GeneratedClip record created (status: APPROVED)
      - If fail: retry with adjusted prompt (up to 3 times)
      - If all retries fail: GeneratedClip (status: NEEDS_REVIEW)
   f. WebSocket event emitted to frontend: clip status update
4. All shots complete → GenerationJob (status: COMPLETE)
5. WebSocket event: job complete
```

### Wan 2.7 API Call

```python
async def generate_wan(
    prompt: str,
    duration: int,
    reference_image_url: str | None,
    first_frame_url: str | None,
    last_frame_url: str | None
) -> str:  # returns clip URL
    
    response = await wan_client.video.generate(
        model="wan2.7-t2v",
        prompt=prompt,
        duration=duration,
        resolution="1080p",
        reference_images=[reference_image_url] if reference_image_url else [],
        first_frame=first_frame_url,
        last_frame=last_frame_url,
    )
    return await poll_until_complete(response.task_id)
```

### HappyHorse 1.1 API Call

```python
async def generate_happyhorse(
    prompt: str,
    duration: int,
    mode: Literal["t2v", "i2v", "s2v", "v2v"],
    reference_image_url: str | None,
    source_video_url: str | None,   # for v2v editing
    edit_instruction: str | None    # for v2v editing
) -> str:
    
    response = await happyhorse_client.video.generate(
        model="happyhorse-1.1-t2v" if mode == "t2v" else f"happyhorse-1.1-{mode}",
        prompt=prompt,
        duration=duration,
        resolution="1080p",
        subject_image=reference_image_url,
        source_video=source_video_url,
        edit_instruction=edit_instruction,
        audio_mode="auto",
    )
    return await poll_until_complete(response.task_id)
```

---

## 7. Storage Architecture (Alibaba Cloud OSS)

```
oss://showmind-{region}/
  projects/
    {project_id}/
      scripts/
        {version}.json                    → structured script JSON
      characters/
        {character_id}/
          reference.jpg                   → uploaded reference image
          embedding.npy                   → face embedding vector
      shots/
        {shot_id}/
          prompt.txt                      → final generation prompt
      clips/
        {clip_id}/
          original.mp4                    → raw generated clip
          trimmed.mp4                     → after user trim
          approved.mp4                    → final approved version
      exports/
        final.mp4                         → stitched final video
        captions.srt                      → subtitle file
        production_report.json            → token usage + cost breakdown
```

**Lifecycle policy:**
- Temp clips (failed consistency, rejected by user): deleted after 7 days
- Approved clips: retained for 30 days post-export
- Final exports: retained for 90 days, then user must download

---

## 8. Deployment on Alibaba Cloud

```yaml
# Infrastructure
compute:
  - type: ECS
    spec: ecs.g7.xlarge (4 vCPU, 16GB RAM)
    count: 2
    region: ap-southeast-1 (Singapore)
    role: API Gateway + Orchestrator

  - type: ECS  
    spec: ecs.g7.large (2 vCPU, 8GB RAM)
    count: 2
    role: Celery workers (video job processing)

storage:
  - type: OSS
    bucket: showmind-assets
    region: ap-southeast-1
    acl: private
    
  - type: RDS PostgreSQL
    spec: rds.pg.s3.large (2 vCPU, 8GB RAM)
    version: 15
    
  - type: Redis (ApsaraDB)
    spec: redis.shard.small
    purpose: Celery broker + session cache

network:
  - type: SLB (Server Load Balancer)
    frontend: HTTPS :443
    backend: HTTP :8000 (FastAPI)
    
  - type: CDN
    origin: OSS bucket
    purpose: Video delivery acceleration

monitoring:
  - CloudMonitor: API latency, error rate, queue depth
  - Log Service: structured application logs
  - ARMS: frontend performance
```

---

## 9. Security

- **Authentication:** JWT (access token 1h, refresh token 30d)
- **OSS access:** presigned URLs (15 minute expiry) — never expose OSS keys to frontend
- **API rate limiting:** 100 req/min per user (enforced at SLB layer)
- **Face data:** embeddings never leave server, reference images in private OSS bucket with per-user ACL
- **Script content:** stored encrypted at rest in RDS
- **CORS:** locked to production domain only
- **Qwen API key:** stored in Alibaba Cloud KMS, injected at runtime via environment variable

---

## 10. Observability

Every pipeline stage emits structured log events:

```json
{
  "timestamp": "2026-06-27T10:00:00Z",
  "project_id": "proj_abc123",
  "stage": "video_generation",
  "shot_id": "shot_007",
  "model": "wan2.7",
  "tokens_used": 0,
  "generation_seconds": 38.2,
  "cost_usd": 0.21,
  "consistency_score": 0.91,
  "retry_count": 0,
  "status": "approved"
}
```

Production report JSON (included with every export) contains full cost audit:
- Total Qwen-Max tokens used
- Total Qwen-VL calls
- Total video seconds generated (Wan vs HappyHorse split)
- Total cost
- Consistency check pass/fail ratio
- Total wall-clock time
