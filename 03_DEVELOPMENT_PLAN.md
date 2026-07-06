> **Historical design doc** from the original build plan — kept for provenance. The shipped architecture (LangGraph agent, model tiering, production bible, set dresser, budget fitting, 9:16 export) is described in [README.md](README.md) and [SUBMISSION.md](SUBMISSION.md).

# Rexgent — Development Plan

**Version:** 1.0  
**Total estimated build time:** 10–12 days (solo) / 5–6 days (2-person team)  
**Deadline:** July 9, 2026 (2:00 PM Pacific Time)

---

## Phase Overview

| Phase | Name | Days | Milestone |
|---|---|---|---|
| 0 | Setup and scaffolding | 0.5 | Repo live, all APIs confirmed working |
| 1 | Script pipeline | 2 | Import + generate + analyze working end-to-end |
| 2 | Character engine | 2 | Character cards, face upload, relationship graph |
| 3 | Storyboard + budget | 1.5 | Shot breakdown, budget dashboard, prompt builder |
| 4 | Video generation | 2 | Wan + HappyHorse + ConsistencyGuard running |
| 5 | Editing loop | 1.5 | Trim, flag, regen, approve, final render |
| 6 | Polish + demo | 1 | Demo script rehearsed, docs complete, video recorded |

---

## Phase 0 — Setup and Scaffolding (Day 0.5)

### Tasks
- [ ] Create GitHub repo (public, MIT license)
- [ ] Set up Next.js 14 frontend (`create-next-app`)
- [ ] Set up FastAPI backend
- [ ] Configure Alibaba Cloud: ECS, OSS, RDS, Redis
- [ ] Register on Qwen Cloud, claim hackathon $40 voucher
- [ ] Test Qwen-Max API call (hello world)
- [ ] Test Wan 2.7 API call (simple text-to-video)
- [ ] Test HappyHorse 1.1 API call
- [ ] Test Qwen-VL API call
- [ ] Set up environment variables + secrets (KMS)
- [ ] Write `CONTRIBUTING.md` and `LICENSE`

### Files to create

```
/
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   └── tsconfig.json
├── backend/
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── .env.example
│   └── alembic.ini
├── .github/
│   └── workflows/
│       └── ci.yml
├── README.md
├── LICENSE
├── CONTRIBUTING.md
└── docker-compose.yml
```

---

## Phase 1 — Script Pipeline (Days 1–3)

### Backend files

```
backend/
├── app/
│   ├── main.py                          → FastAPI app entry point
│   ├── config.py                        → settings, env vars
│   ├── database.py                      → SQLAlchemy setup
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── project.py                   → Project ORM model
│   │   ├── script.py                    → Script, Scene ORM models
│   │   └── plot_flag.py                 → PlotFlag ORM model
│   │
│   ├── schemas/
│   │   ├── script.py                    → Pydantic: ScriptCreate, ScriptResponse
│   │   ├── plot_flag.py                 → Pydantic: PlotFlagResponse
│   │   └── ending.py                    → Pydantic: EndingAnalysis, EndingOption
│   │
│   ├── routers/
│   │   └── script.py                    → /api/script/* endpoints
│   │
│   ├── services/
│   │   ├── script_parser.py             → PDF/Word → raw text extraction
│   │   ├── script_structurer.py         → raw text → structured JSON via Qwen-Max
│   │   └── script_generator.py          → premise → full script via Qwen-Max
│   │
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── orchestrator.py              → RexgentOrchestrator class
│   │   └── memory_graph.py              → NarrativeMemoryGraph dataclass
│   │
│   └── mcp_tools/
│       ├── __init__.py
│       ├── plot_gap_detector.py         → PlotGapDetector MCP tool
│       ├── ending_engine.py             → EndingEngine MCP tool
│       └── narrative_judge.py           → NarrativeJudge MCP tool
│
├── migrations/
│   └── versions/
│       └── 001_initial.py               → Alembic migration: all tables
│
└── tests/
    ├── test_script_parser.py
    ├── test_script_structurer.py
    └── test_plot_gap_detector.py
```

### Frontend files

```
frontend/
├── app/
│   ├── layout.tsx                       → root layout, providers
│   ├── page.tsx                         → landing / project list
│   └── projects/
│       └── [id]/
│           └── script/
│               ├── page.tsx             → script editor page
│               └── loading.tsx
│
├── components/
│   └── script/
│       ├── ScriptEditor.tsx             → Monaco editor wrapper
│       ├── ScriptImport.tsx             → PDF/Word drag-drop uploader
│       ├── ScriptGenerate.tsx           → premise form + generate button
│       ├── PlotGapPanel.tsx             → flag list + inline annotations
│       ├── EndingGraph.tsx              → D3 branching ending graph
│       └── NarrativeJudgeReport.tsx     → quality score display
│
├── hooks/
│   ├── useScript.ts                     → React Query script data hooks
│   └── usePlotAnalysis.ts               → plot gap + ending analysis hooks
│
├── lib/
│   ├── api.ts                           → API client (axios instance)
│   └── types/
│       ├── script.ts                    → TypeScript types for script data
│       └── plot_flag.ts                 → TypeScript types for flags
│
└── stores/
    └── projectStore.ts                  → Zustand project state store
```

### Key prompts (Qwen-Max system prompts)

```
backend/prompts/
├── script_structure.txt                 → parse raw script into JSON schema
├── script_generate.txt                  → generate script from premise
├── plot_gap_detect.txt                  → detect narrative problems
├── ending_analyse.txt                   → analyse ending completeness
└── narrative_judge.txt                  → score script on 5 axes
```

---

## Phase 2 — Character Engine (Days 3–5)

### Backend files

```
backend/app/
├── models/
│   ├── character.py                     → Character ORM model (incl. face_embedding JSONB)
│   └── relationship.py                  → CharacterRelationship ORM model
│
├── schemas/
│   ├── character.py                     → Pydantic: CharacterCreate, CharacterResponse
│   └── relationship.py                  → Pydantic: RelationshipGraph
│
├── routers/
│   ├── character.py                     → /api/characters/* endpoints
│   └── graph.py                         → /api/graph/* endpoints
│
├── services/
│   ├── character_extractor.py           → script → character list via Qwen-Max
│   ├── mbti_inferrer.py                 → character → MBTI via Qwen-Max
│   ├── face_embedder.py                 → image → embedding via Qwen-VL
│   ├── appearance_generator.py          → traits → visual description via Qwen-Max
│   └── relationship_builder.py          → script + chars → relationship graph via Qwen-Max
│
└── mcp_tools/
    └── consistency_guard.py             → ConsistencyGuard MCP tool (Qwen-VL)
```

### Frontend files

```
frontend/
├── app/projects/[id]/characters/
│   ├── page.tsx                         → character engine page
│   └── [characterId]/
│       └── page.tsx                     → individual character detail
│
├── components/characters/
│   ├── CharacterCard.tsx                → full profile card with all fields
│   ├── CharacterList.tsx                → grid of all character cards
│   ├── FaceUpload.tsx                   → image upload + Qwen-VL status
│   ├── AppearanceGenerator.tsx          → AI generate appearance button + result
│   ├── MBTIBadge.tsx                    → MBTI display with tooltip explanation
│   ├── RelationshipGraph.tsx            → D3 force-directed character graph
│   ├── RelationshipEdgePanel.tsx        → slide-out panel for edge evidence
│   └── SceneGraph.tsx                   → D3 scene dependency graph
│
└── hooks/
    ├── useCharacters.ts                 → character CRUD hooks
    ├── useFaceEmbed.ts                  → face upload + embedding status
    └── useRelationshipGraph.ts          → graph data hooks
```

### Key prompts

```
backend/prompts/
├── character_extract.txt                → extract character list from script
├── mbti_infer.txt                       → infer MBTI from dialogue + behaviour
├── relationship_extract.txt             → extract character relationships as triples
└── appearance_generate.txt             → generate visual description from personality
```

---

## Phase 3 — Storyboard and Budget (Days 5–6.5)

### Backend files

```
backend/app/
├── models/
│   ├── shot.py                          → Shot ORM model (all storyboard fields)
│   └── generation_job.py               → GenerationJob ORM model
│
├── schemas/
│   ├── shot.py                          → Pydantic: ShotCreate, ShotResponse, ScoredShot
│   └── budget.py                        → Pydantic: BudgetPlan, CostForecast
│
├── routers/
│   ├── storyboard.py                    → /api/storyboard/* endpoints
│   └── budget.py                        → /api/budget/* endpoints
│
├── services/
│   ├── storyboard_generator.py          → scene → shots via Qwen-Max
│   └── budget_calculator.py            → shots → cost forecast
│
└── mcp_tools/
    ├── scene_prompt_craft.py            → ScenePromptCraft MCP tool
    └── token_optimizer.py              → TokenOptimizer MCP tool
```

### Frontend files

```
frontend/
├── app/projects/[id]/storyboard/
│   └── page.tsx                         → storyboard + budget page
│
├── components/storyboard/
│   ├── StoryboardView.tsx               → full storyboard with all scenes
│   ├── SceneSection.tsx                 → collapsible section per scene
│   ├── ShotCard.tsx                     → individual shot card (editable)
│   ├── ShotEditor.tsx                   → inline edit mode for shot fields
│   ├── BudgetDashboard.tsx              → token budget overview card
│   ├── BudgetBreakdown.tsx              → scene-level cost breakdown table
│   ├── QualityTierBadge.tsx             → Wan/HappyHorse visual indicator
│   └── QualityTierOverride.tsx          → manual tier change UI
│
└── hooks/
    ├── useStoryboard.ts                 → storyboard CRUD hooks
    └── useBudget.ts                     → budget calculation hooks
```

### Key prompts

```
backend/prompts/
├── storyboard_generate.txt              → scene → shot breakdown with all fields
└── scene_prompt_craft.txt              → shot data → cinematic video prompt
```

---

## Phase 4 — Video Generation (Days 6.5–8.5)

### Backend files

```
backend/app/
├── models/
│   └── generated_clip.py                → GeneratedClip ORM model
│
├── schemas/
│   └── generation.py                    → Pydantic: GenerationJobStatus, ClipResult
│
├── routers/
│   └── generation.py                    → /api/generate/* endpoints
│
├── services/
│   ├── wan_client.py                    → Wan 2.7 API wrapper (async)
│   ├── happyhorse_client.py             → HappyHorse 1.1 API wrapper (async)
│   ├── generation_runner.py             → main generation orchestration loop
│   └── oss_manager.py                   → Alibaba Cloud OSS upload/download/presign
│
├── workers/
│   ├── celery_app.py                    → Celery + Redis setup
│   ├── generation_worker.py             → Celery task: process generation job
│   └── consistency_worker.py           → Celery task: run ConsistencyGuard
│
└── websocket/
    └── ws_manager.py                    → WebSocket connection manager + event emitter
```

### Frontend files

```
frontend/
├── app/projects/[id]/generate/
│   └── page.tsx                         → generation dashboard page
│
├── components/generate/
│   ├── GenerationLauncher.tsx           → pre-flight check + start button
│   ├── GenerationQueue.tsx              → live list of all shots with status
│   ├── ClipProgressCard.tsx             → individual clip: model, status, ETA
│   ├── ConsistencyBadge.tsx             → pass/retry/fail/needs-review badge
│   ├── GenerationSummary.tsx            → completed job summary card
│   └── CostTracker.tsx                  → live cost counter during generation
│
└── hooks/
    ├── useGeneration.ts                 → generation job hooks
    └── useWebSocket.ts                  → WebSocket connection + events
```

---

## Phase 5 — Editing Loop (Days 8.5–10)

### Backend files

```
backend/app/
├── models/
│   ├── edit_flag.py                     → EditFlag ORM model
│   └── final_export.py                  → FinalExport ORM model
│
├── schemas/
│   ├── edit.py                          → Pydantic: TrimRequest, FlagRequest, RegenRequest
│   └── export.py                        → Pydantic: ExportResult
│
├── routers/
│   ├── edit.py                          → /api/edit/* endpoints
│   └── export.py                        → /api/export/* endpoints
│
├── services/
│   ├── video_trimmer.py                 → FFmpeg trim operations
│   ├── regen_prompt_rewriter.py         → flag → improved prompt via Qwen-Max
│   ├── video_stitcher.py               → FFmpeg final assembly
│   └── caption_generator.py            → script dialogue → .srt via Qwen-TTS
│
└── workers/
    └── export_worker.py                 → Celery task: FFmpeg render + upload to OSS
```

### Frontend files

```
frontend/
├── app/projects/[id]/edit/
│   └── page.tsx                         → video editor page
│
├── components/edit/
│   ├── Timeline.tsx                     → horizontal clip timeline
│   ├── TimelineClip.tsx                 → individual clip on timeline
│   ├── TrimHandles.tsx                  → drag handles for trim selection
│   ├── ClipViewer.tsx                   → video player with playback controls
│   ├── FlagPanel.tsx                    → change instruction form (flag type + text)
│   ├── RegenComparison.tsx              → A/B comparison: original vs regen
│   ├── ApprovalButtons.tsx              → approve / reject / regen again
│   └── ExportPanel.tsx                  → final render trigger + download
│
└── hooks/
    ├── useTrim.ts                       → trim state + extract logic
    ├── useEditFlag.ts                   → flag submission + regen tracking
    └── useExport.ts                     → export job status + download URL
```

### Key prompts

```
backend/prompts/
└── regen_prompt_rewrite.txt            → original prompt + flag → improved prompt
```

---

## Phase 6 — Polish and Demo (Days 10–11)

### Tasks
- [ ] Write full `README.md` with setup instructions
- [ ] Write `ARCHITECTURE.md` with diagram (this file)
- [ ] Record 3-minute demo video (follow demo script from Product Spec §8)
- [ ] Deploy to Alibaba Cloud ECS (production)
- [ ] Test full end-to-end flow with demo script
- [ ] Capture Alibaba Cloud deployment proof (screenshot/recording)
- [ ] Write blog post for bonus prize
- [ ] Submit on Devpost

### Demo files

```
demo/
├── demo_script.md                       → step-by-step demo narration script
├── sample_premise.txt                   → "A detective in 2047 Tokyo..."
├── sample_script.pdf                    → pre-written 3-scene script for import demo
└── character_photos/
    ├── detective.jpg                    → reference image for main character
    └── ai_partner.jpg                   → reference image for AI partner character
```

---

## All Files — Complete Index

### Backend (Python / FastAPI)

```
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── project.py
│   │   ├── script.py
│   │   ├── plot_flag.py
│   │   ├── character.py
│   │   ├── relationship.py
│   │   ├── shot.py
│   │   ├── generation_job.py
│   │   ├── generated_clip.py
│   │   ├── edit_flag.py
│   │   └── final_export.py
│   │
│   ├── schemas/
│   │   ├── script.py
│   │   ├── plot_flag.py
│   │   ├── ending.py
│   │   ├── character.py
│   │   ├── relationship.py
│   │   ├── shot.py
│   │   ├── budget.py
│   │   ├── generation.py
│   │   ├── edit.py
│   │   └── export.py
│   │
│   ├── routers/
│   │   ├── script.py
│   │   ├── character.py
│   │   ├── graph.py
│   │   ├── storyboard.py
│   │   ├── budget.py
│   │   ├── generation.py
│   │   ├── edit.py
│   │   └── export.py
│   │
│   ├── services/
│   │   ├── script_parser.py
│   │   ├── script_structurer.py
│   │   ├── script_generator.py
│   │   ├── character_extractor.py
│   │   ├── mbti_inferrer.py
│   │   ├── face_embedder.py
│   │   ├── appearance_generator.py
│   │   ├── relationship_builder.py
│   │   ├── storyboard_generator.py
│   │   ├── budget_calculator.py
│   │   ├── wan_client.py
│   │   ├── happyhorse_client.py
│   │   ├── generation_runner.py
│   │   ├── oss_manager.py
│   │   ├── video_trimmer.py
│   │   ├── regen_prompt_rewriter.py
│   │   ├── video_stitcher.py
│   │   └── caption_generator.py
│   │
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   └── memory_graph.py
│   │
│   ├── mcp_tools/
│   │   ├── __init__.py
│   │   ├── plot_gap_detector.py
│   │   ├── ending_engine.py
│   │   ├── narrative_judge.py
│   │   ├── consistency_guard.py
│   │   ├── scene_prompt_craft.py
│   │   └── token_optimizer.py
│   │
│   ├── workers/
│   │   ├── celery_app.py
│   │   ├── generation_worker.py
│   │   ├── consistency_worker.py
│   │   └── export_worker.py
│   │
│   └── websocket/
│       └── ws_manager.py
│
├── prompts/
│   ├── script_structure.txt
│   ├── script_generate.txt
│   ├── plot_gap_detect.txt
│   ├── ending_analyse.txt
│   ├── narrative_judge.txt
│   ├── character_extract.txt
│   ├── mbti_infer.txt
│   ├── relationship_extract.txt
│   ├── appearance_generate.txt
│   ├── storyboard_generate.txt
│   ├── scene_prompt_craft.txt
│   └── regen_prompt_rewrite.txt
│
├── migrations/
│   ├── env.py
│   └── versions/
│       └── 001_initial.py
│
└── tests/
    ├── conftest.py
    ├── test_script_parser.py
    ├── test_script_structurer.py
    ├── test_plot_gap_detector.py
    ├── test_character_extractor.py
    ├── test_face_embedder.py
    ├── test_relationship_builder.py
    ├── test_storyboard_generator.py
    ├── test_token_optimizer.py
    ├── test_wan_client.py
    ├── test_happyhorse_client.py
    ├── test_consistency_guard.py
    └── test_regen_rewriter.py
```

### Frontend (Next.js / TypeScript)

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── globals.css
│   └── projects/
│       ├── page.tsx
│       └── [id]/
│           ├── layout.tsx
│           ├── script/
│           │   ├── page.tsx
│           │   └── loading.tsx
│           ├── characters/
│           │   ├── page.tsx
│           │   └── [characterId]/page.tsx
│           ├── storyboard/
│           │   └── page.tsx
│           ├── generate/
│           │   └── page.tsx
│           ├── edit/
│           │   └── page.tsx
│           └── export/
│               └── page.tsx
│
├── components/
│   ├── script/
│   │   ├── ScriptEditor.tsx
│   │   ├── ScriptImport.tsx
│   │   ├── ScriptGenerate.tsx
│   │   ├── PlotGapPanel.tsx
│   │   ├── EndingGraph.tsx
│   │   └── NarrativeJudgeReport.tsx
│   ├── characters/
│   │   ├── CharacterCard.tsx
│   │   ├── CharacterList.tsx
│   │   ├── FaceUpload.tsx
│   │   ├── AppearanceGenerator.tsx
│   │   ├── MBTIBadge.tsx
│   │   ├── RelationshipGraph.tsx
│   │   ├── RelationshipEdgePanel.tsx
│   │   └── SceneGraph.tsx
│   ├── storyboard/
│   │   ├── StoryboardView.tsx
│   │   ├── SceneSection.tsx
│   │   ├── ShotCard.tsx
│   │   ├── ShotEditor.tsx
│   │   ├── BudgetDashboard.tsx
│   │   ├── BudgetBreakdown.tsx
│   │   ├── QualityTierBadge.tsx
│   │   └── QualityTierOverride.tsx
│   ├── generate/
│   │   ├── GenerationLauncher.tsx
│   │   ├── GenerationQueue.tsx
│   │   ├── ClipProgressCard.tsx
│   │   ├── ConsistencyBadge.tsx
│   │   ├── GenerationSummary.tsx
│   │   └── CostTracker.tsx
│   ├── edit/
│   │   ├── Timeline.tsx
│   │   ├── TimelineClip.tsx
│   │   ├── TrimHandles.tsx
│   │   ├── ClipViewer.tsx
│   │   ├── FlagPanel.tsx
│   │   ├── RegenComparison.tsx
│   │   ├── ApprovalButtons.tsx
│   │   └── ExportPanel.tsx
│   └── shared/
│       ├── TokenBudgetBar.tsx
│       ├── QwenModelBadge.tsx
│       ├── ProjectNav.tsx
│       ├── LoadingSpinner.tsx
│       └── ErrorBoundary.tsx
│
├── hooks/
│   ├── useScript.ts
│   ├── usePlotAnalysis.ts
│   ├── useCharacters.ts
│   ├── useFaceEmbed.ts
│   ├── useRelationshipGraph.ts
│   ├── useStoryboard.ts
│   ├── useBudget.ts
│   ├── useGeneration.ts
│   ├── useWebSocket.ts
│   ├── useTrim.ts
│   ├── useEditFlag.ts
│   └── useExport.ts
│
├── lib/
│   ├── api.ts
│   ├── websocket.ts
│   └── types/
│       ├── script.ts
│       ├── plot_flag.ts
│       ├── character.ts
│       ├── relationship.ts
│       ├── shot.ts
│       ├── budget.ts
│       ├── generation.ts
│       ├── edit.ts
│       └── export.ts
│
└── stores/
    ├── projectStore.ts
    ├── scriptStore.ts
    ├── characterStore.ts
    ├── generationStore.ts
    └── editStore.ts
```

### Documentation

```
docs/
├── 01_PRODUCT_SPEC.md                   → this file (full feature spec)
├── 02_ARCHITECTURE.md                   → system architecture
├── 03_DEVELOPMENT_PLAN.md               → this development plan
├── 04_API_REFERENCE.md                  → all API endpoints documented
├── 05_QWEN_PROMPTS.md                   → all Qwen-Max prompt templates
├── 06_MCP_TOOLS.md                      → MCP tool specs and schemas
├── 07_CHARACTER_ENGINE.md               → character system deep dive
├── 08_NARRATIVE_MEMORY_GRAPH.md         → memory graph design
├── 09_VIDEO_GENERATION_PIPELINE.md      → generation pipeline details
├── 10_BUDGET_SYSTEM.md                  → token budget design
├── 11_EDITING_LOOP.md                   → edit loop UX and logic
└── 12_DEPLOYMENT_GUIDE.md              → Alibaba Cloud setup
```

---

## Priority Order (If Time Runs Short)

If the deadline is tight, build in this priority order to ensure a demoable product:

1. **Must have (core demo):**
   - Script generation from premise (Qwen-Max)
   - Character extraction + MBTI (Qwen-Max)
   - Face upload + embedding (Qwen-VL)
   - Storyboard generation (Qwen-Max)
   - Video generation with Wan + HappyHorse
   - ConsistencyGuard basic version
   - Token budget dashboard

2. **Should have (impressive demo):**
   - Plot gap detector with inline flags
   - Relationship graph (D3)
   - Editing loop (trim + flag + regen)
   - Final render + export

3. **Nice to have (bonus points):**
   - Ending engine branching graph
   - Scene dependency graph
   - MBTI confidence score display
   - Production report JSON in export
   - Full A/B regen comparison UI
