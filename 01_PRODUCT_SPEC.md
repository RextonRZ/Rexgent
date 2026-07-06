> **Historical design doc** from the original build plan — kept for provenance. The shipped architecture (LangGraph agent, model tiering, production bible, set dresser, budget fitting, 9:16 export) is described in [README.md](README.md) and [SUBMISSION.md](SUBMISSION.md).

# Rexgent — Product Specification

**Version:** 1.0  
**Track:** Global AI Hackathon Series with Qwen Cloud — Track 2: AI Showrunner  
**Prize Target:** $7,000 cash + $3,000 cloud credits  
**Tagline:** Give me a story idea. I'll hand you back a short drama.

---

## 1. Problem Statement

Creating a short drama today means bouncing between 5–10 tools: a writing app, a storyboard tool, an image generator for characters, a video generation API, a video editor, a caption tool. Every handoff loses context. Characters drift visually between scenes. Plot holes only get caught during editing — too late. Solo creators and small studios waste 80% of their time on orchestration, not storytelling.

**Rexgent collapses the entire pipeline into one AI-native workspace.** From a single premise or an imported script, it autonomously handles scriptwriting, character building, storyboarding, video generation, and iterative editing — with a live token budget dashboard and a narrative intelligence layer that catches problems before they become expensive.

---

## 2. Target Users

| User Type | Pain Point | How Rexgent Solves It |
|---|---|---|
| Solo indie creator | No production team, too many tools | End-to-end pipeline in one workspace |
| Small content studio | Character inconsistency across episodes | Face-lock system via Qwen-VL |
| Brand content team | Script → video takes days | Auto-storyboard + budget-aware generation |
| Film student | Plot holes caught too late | Real-time gap detector + ending engine |
| Localisation team | Recreating scenes for different markets | Character bible + prompt DSL reuse |

---

## 3. Core User Flows

### Flow A — Import existing script

```
User uploads PDF or Word script
  → Qwen-Max parses and structures it (acts, scenes, dialogue)
  → Auto-extracts character list with traits
  → Runs plot gap detector (flags unclear motivations, missing scenes)
  → Runs ending detector (confirms ending exists or surfaces alternatives)
  → Builds character relationship graph with plot evidence
  → User reviews, edits, approves
  → Proceeds to storyboarding
```

### Flow B — Write from scratch

```
User enters: genre + premise (1–3 sentences) + target length
  → Qwen-Max generates full script with act structure
  → Same analysis pipeline as Flow A kicks in automatically
  → User can edit any scene inline before proceeding
```

### Flow C — Add and configure characters

```
Characters auto-extracted (or manually added)
  → User uploads reference photo for each character (optional but powerful)
  → Qwen-VL extracts face embedding → stored in character bible
  → Qwen-Max infers MBTI, speech patterns, emotional arc
  → User can adjust all fields manually
  → Character relationship graph auto-renders
  → AI generate button: produces character appearance description card
```

### Flow D — Storyboard + budget plan

```
Approved script → Qwen-Max breaks into shot-by-shot storyboard
  → Each scene gets: shot type, camera angle, lighting mood, colour palette note
  → TokenOptimizer scores each scene by emotional weight (0–10)
  → High-score scenes → Wan 2.7 (premium quality)
  → Low-score scenes → HappyHorse 1.1 (fast, cheap)
  → Budget dashboard shows: total cost estimate, seconds of video, scenes allocated
  → User can manually override any scene's quality tier
```

### Flow E — Video generation

```
Storyboard approved → ScenePromptCraft converts each shot into cinematic prompt
  → Each prompt includes: character description + face reference + shot type + mood
  → Wan 2.7 called for hero scenes (async, queued)
  → HappyHorse 1.1 called for draft scenes (faster turnaround)
  → ConsistencyGuard runs Qwen-VL on each returned frame
      → Face similarity check against character bible
      → If below threshold: auto-retry with corrected seed + stronger face constraint
  → Progress dashboard updates in real time
```

### Flow F — Editing loop

```
All clips generated → Editor view opens
  → User watches assembled video with scene markers
  → For any unsatisfying scene:
      1. Trim: drag to select the bad segment
      2. Extract: isolate the clip
      3. Flag: type what needs to change ("make the lighting darker", "character looks wrong")
      4. Regen: Rexgent rewrites the prompt + regenerates just that clip
      5. Repeat until satisfied
  → Final render: clips stitched, captions added, audio synced
  → Export as MP4
```

---

## 4. Feature Breakdown

### 4.1 Script Input

**Import script (PDF / Word / .txt)**
- Supports PDF via PyMuPDF text extraction
- Supports .docx via python-docx
- Qwen-Max parses raw text into structured JSON: `{acts[], scenes[], characters[], dialogue[]}`
- Preserves scene numbers and stage directions

**Write from scratch**
- Input fields: genre (dropdown), premise (textarea, max 300 chars), tone, target episode count, target length per episode
- Qwen-Max generates full formatted screenplay in standard format
- Markdown editor for inline editing post-generation

### 4.2 AI Script Intelligence

**Plot gap detector**
- Qwen-Max reads the full script and returns a JSON array of flags
- Flag types:
  - `MISSING_MOTIVATION` — character does something without established reason
  - `CONTINUITY_BREAK` — fact established in Scene X contradicted in Scene Y
  - `UNRESOLVED_THREAD` — subplot introduced but never closed
  - `PACING_ISSUE` — scene has no narrative function
- Each flag includes: scene number, line reference, description, suggested fix
- Rendered as inline annotations in the script editor (like code linting)

**Ending engine**
- Checks final act for resolution of: main conflict, character arcs, key subplots
- If incomplete: generates 3 possible endings as a branching graph
- Each ending node shows: summary, emotional tone, compatibility score with existing arc
- User can select one or ask AI to blend two endings
- User can also paste their own ending and ask AI to check compatibility

**Narrative memory graph**
- Persistent state object shared across all AI calls in the session
- Tracks: character states per scene, established facts, visual motifs, tension curve
- Every Qwen call reads from and writes to this graph
- Prevents contradictions between script, storyboard, and video generation prompts

### 4.3 Character Engine

**Auto-extraction**
- From imported or generated script, Qwen-Max extracts:
  - Character name
  - First appearance scene
  - Role (protagonist / antagonist / supporting)
  - Key dialogue samples (up to 5 lines)
  - Physical descriptions mentioned in script
  - Emotional arc summary

**Character card**
Each character gets a structured profile:
```
Name: [name]
Role: [protagonist/antagonist/supporting]
Age: [inferred or specified]
Physical description: [text + AI-generated visual keywords]
Personality: [Qwen-Max generated paragraph]
MBTI: [inferred from dialogue patterns, e.g. INTJ]
Speech pattern: [formal/casual/terse/verbose]
Emotional arc: [beginning state → midpoint state → ending state]
Reference image: [uploaded by user, optional]
Face embedding: [Qwen-VL extracted vector, stored internally]
Visual prompt keywords: [used in every scene this character appears in]
```

**Reference image upload + face lock**
- User uploads any photo of a real person or AI-generated character image
- Qwen-VL processes the image and extracts:
  - Facial embedding (stored as vector in character bible)
  - Visual description: skin tone, hair, distinctive features, style
- This description is injected into every video generation prompt that includes this character
- ConsistencyGuard validates every generated frame against this embedding
- If face similarity score < 0.75: frame is flagged, clip is auto-retried with seed adjustment

**AI appearance generator**
- If no reference image uploaded: user can click "Generate appearance"
- Qwen-Max generates a detailed visual description from personality + role + setting
- User can edit the description before it gets locked into character bible
- Optional: generate a reference image via Wan or HappyHorse image mode to use as visual anchor

**MBTI inference**
- Qwen-Max analyses dialogue patterns, decision-making in plot, and relationships
- Returns MBTI type with confidence score and reasoning
- Displayed on character card as a tag (e.g. `INTJ — 87% confidence`)
- Users can override manually

### 4.4 Relationship and Scene Graph

**Character relationship graph**
- Nodes: each character
- Edges: relationship type (romantic / rival / family / mentor / ally / enemy)
- Each edge is annotated with:
  - Relationship strength (1–10)
  - First established scene
  - Evidence quote from script
  - How relationship evolves (static / grows / breaks)
- Rendered as interactive force-directed graph (D3.js or vis.js)
- Clicking an edge shows a side panel with all plot evidence

**Scene dependency graph**
- Nodes: each scene
- Edges: plot dependency (Scene 3 requires setup from Scene 1)
- Character nodes overlap: shows which characters appear in which scenes
- Useful for detecting if reordering scenes would break continuity
- AI can suggest optimal scene ordering for pacing

**Unified graph view toggle**
- Characters view: shows only characters and their relationships
- Scenes view: shows only scenes and dependencies
- Combined view: shows both, with character nodes smaller and scene nodes larger

### 4.5 Storyboarding

**Auto-storyboard generation**
- For each scene in the script, Qwen-Max generates:
  - Shot count (how many individual clips this scene needs)
  - For each shot:
    - Shot type: ECU / CU / MCU / MS / FS / LS / EWS / POV / OTS
    - Camera movement: static / pan / tilt / dolly / handheld / drone
    - Lighting: natural / golden hour / night / overcast / dramatic / neon
    - Colour mood: warm / cool / desaturated / high contrast / pastel
    - Characters in frame: list of character names
    - Action description: what happens in this shot (1–2 sentences)
    - Emotional beat: what the audience should feel
    - Estimated duration: 3–15 seconds

**Storyboard editor**
- Each shot shown as a card with all fields editable
- User can drag to reorder shots within a scene
- User can add or delete shots
- "Director's note" field for any creative instruction that should influence generation

### 4.6 Token Budget Dashboard

**Scene scoring**
- TokenOptimizer MCP tool assigns each scene an importance score (0–10) based on:
  - Is it a climax or turning point? (+3)
  - Does it introduce a major character? (+2)
  - Is it a dialogue-heavy scene that needs clear facial expressions? (+2)
  - Is it a transitional / establishing shot? (+0)
  - Is it an action sequence? (+2)
  - Requested duration: longer = higher cost

**Quality tier assignment**
- Score 7–10 → Wan 2.7 (high quality, ~$0.07/sec)
- Score 4–6 → HappyHorse 1.1 (balanced, ~$0.05/sec)
- Score 0–3 → HappyHorse 1.1 fast mode (draft quality, lowest cost)

**Budget dashboard UI**
- Total scenes: N
- Total estimated video seconds: N
- Breakdown: N scenes at Wan, N scenes at HappyHorse
- Estimated total cost: $X.XX
- Remaining free credit: $X.XX
- Projected overage (if any): $X.XX
- User can drag scenes between tiers to manually rebalance
- Budget warning banner if projected cost exceeds available credit

### 4.7 Video Generation

**ScenePromptCraft MCP tool**
- Takes storyboard shot data + character bible entries
- Produces a structured cinematic prompt for Wan/HappyHorse
- Prompt structure:
  ```
  [shot_type], [camera_movement], [subject_description_with_face_keywords],
  [action], [lighting], [colour_mood], [audio_mood], [duration]s
  ```
- Character names are never used in prompts — replaced by full visual descriptions
- Example output:
  ```
  Close-up, static camera, young East Asian woman with sharp cheekbones and short 
  black hair in a leather jacket, turns slowly to face camera with cold expression, 
  dramatic side lighting, desaturated blue tones, tense ambient score, 5s
  ```

**Wan 2.7 integration**
- Text-to-video and image-to-video modes
- First-and-last frame control for seamless clip stitching
- 1080p, up to 15 seconds per clip
- Character reference image passed alongside text prompt for visual anchoring
- Async queue with polling — UI shows progress per clip

**HappyHorse 1.1 integration**
- Text-to-video (T2V), Image-to-video (I2V), Subject-to-video (S2V)
- S2V mode: pass character reference image directly as subject anchor
- Video-to-video (V2V) editing mode used in the edit loop
- Native audio generation: lip-sync + ambient sound in one pass
- Faster turnaround for draft and transition scenes

**ConsistencyGuard MCP tool**
- After each clip is returned, runs Qwen-VL on 3 sampled frames (start, mid, end)
- Compares face embedding against stored character bible vector
- Similarity score threshold: 0.75 (configurable)
- On pass: clip marked ✓ and added to assembly queue
- On fail: logs failure reason, adjusts prompt (stronger face description + seed randomisation), retries up to 3 times
- If all 3 retries fail: clip flagged for manual review, lower-quality fallback used

### 4.8 Editing Loop

**Timeline editor**
- All generated clips assembled in order on a horizontal timeline
- Each clip shows: scene number, character(s) in frame, duration, quality tier, consistency score
- Click any clip to open the clip detail panel

**Trim**
- Drag handles on clip to select start and end points
- Preview the trimmed clip before extracting

**Extract and flag**
- Extract: isolates the selected segment as a new clip
- Flag panel opens with fields:
  - What's wrong? (free text, e.g. "character face looks nothing like reference")
  - Change type: `APPEARANCE` / `ACTION` / `LIGHTING` / `AUDIO` / `TIMING` / `OTHER`
  - Severity: `MINOR` / `MAJOR` / `REGENERATE_FULLY`
  - Additional direction: any extra instruction for the next generation attempt

**Regen loop**
- Rexgent rewrites the original prompt based on the flag description
- Calls Qwen-Max to incorporate the change instruction into the prompt
- Regenerates only the flagged clip (not the whole scene)
- New clip appears alongside old clip for A/B comparison
- User selects preferred version or asks for another iteration
- Loop continues until user approves

**Final render**
- All approved clips stitched in order via FFmpeg
- Captions generated from script dialogue using Qwen TTS transcript
- Audio: HappyHorse native audio or Qwen TTS voiceover (configurable)
- Export format: MP4, 1080p, with optional subtitle track (.srt)

---

## 5. AI and Qwen Tech Stack

| Component | Qwen Model / Tool | Purpose |
|---|---|---|
| Master orchestrator | Qwen-Max | Coordinates all pipeline stages, manages narrative memory graph |
| Script parsing | Qwen-Max | Structures raw script text into JSON schema |
| Plot gap detection | Qwen-Max | Identifies narrative problems, generates fix suggestions |
| Ending engine | Qwen-Max | Detects missing endings, generates branching alternatives |
| Character extraction | Qwen-Max | Extracts and profiles all characters from script |
| MBTI inference | Qwen-Max | Analyses dialogue patterns for personality classification |
| Relationship graph | Qwen-Max | Extracts character relationship triples with evidence |
| Storyboard generation | Qwen-Max | Converts scenes to shot-by-shot cinematic breakdown |
| ScenePromptCraft | Qwen-Max | Translates storyboard data into video generation prompts |
| Face embedding | Qwen-VL | Extracts facial features from uploaded reference images |
| ConsistencyGuard | Qwen-VL | Validates generated frames against character face embeddings |
| Hero scene video | Wan 2.7 | High-quality 1080p video for climax and key scenes |
| Draft/transition video | HappyHorse 1.1 | Fast video generation with native audio for supporting scenes |
| Video editing | HappyHorse 1.1 V2V | Video-to-video regeneration in the edit loop |
| Regen prompt rewriter | Qwen-Max | Incorporates user flags into improved generation prompts |
| Caption generation | Qwen TTS | Generates dialogue captions from script |

### Custom MCP Tools

| Tool | Description |
|---|---|
| `ScenePromptCraft` | Cinematic prompt DSL builder — converts storyboard shot data into optimised Wan/HappyHorse prompts |
| `ConsistencyGuard` | Frame-level face similarity validator using Qwen-VL embeddings |
| `TokenOptimizer` | Budget-aware scene scoring and quality tier assignment |
| `NarrativeJudge` | LLM-as-critic: evaluates script quality on 5 axes before generation begins |
| `PlotGapDetector` | Structured narrative analysis tool — returns typed flags with scene references |
| `EndingEngine` | Ending completeness checker and branching alternative generator |

---

## 6. Non-Functional Requirements

### Performance
- Script parsing: < 10 seconds for scripts up to 120 pages
- Storyboard generation: < 30 seconds for a 3-episode series
- Video generation: async — estimated 30–60 seconds per clip (Wan), 15–30 seconds (HappyHorse)
- ConsistencyGuard check: < 5 seconds per clip
- UI responsiveness: all non-generation actions < 200ms

### Reliability
- Video generation failures handled gracefully: auto-retry (up to 3 times), then fallback to lower tier
- Script parsing failures: show raw text with manual structured input fallback
- All state persisted to Alibaba Cloud OSS — session resumable after browser close

### Cost control
- Token budget enforced before generation starts (hard stop if projected cost > available credit + buffer)
- User must confirm before generation begins if cost > $5
- Real-time cost tracking during generation — pause available at any time

### Security
- Reference images stored in private Alibaba Cloud OSS bucket (per-user, not shared)
- Face embeddings stored server-side only, never transmitted to frontend
- Scripts and generated videos owned by the user, not retained after session export

---

## 7. Out of Scope (v1.0)

- Multi-user collaboration on the same project
- Real-time co-editing
- Publishing directly to TikTok / YouTube / Instagram
- Music generation (audio uses HappyHorse native audio or TTS only)
- Multi-language script input (English only for v1.0)

**Note on length:** Episode count is not hard-capped. Scriptwriting is cheap (Qwen-Max text), so users can write many episodes. The token budget governs how much *video* is rendered — not how much script is written. The storyboard + budget stage allocates the available credit ($40 voucher) across shots, and the cost circuit breaker stops generation before overrun. For the demo, a focused 1–3 episode slice is rendered to keep the submission video under 3 minutes.

---

## 8. Success Metrics for Hackathon Demo

The demo should show a judge this sequence in under 3 minutes:

1. Paste a one-line premise: *"A detective in 2047 Tokyo discovers her partner is an AI."*
2. Rexgent generates a 3-scene script in real time
3. Plot gap detector flags one issue (AI partner's origin is unestablished)
4. AI fixes it with one click
5. Character cards appear — user uploads a reference photo for the detective
6. Relationship graph renders (detective ↔ AI partner: trust → betrayal arc)
7. Storyboard generates with budget breakdown (2 Wan scenes, 1 HappyHorse scene)
8. Generation runs — live progress dashboard
9. One clip fails ConsistencyGuard (face drift) → auto-retried → passes
10. User trims one scene, flags "lighting too bright", regenerates → approves
11. Final render plays — 45 seconds of coherent short drama from a one-liner

That demo sequence answers every judging criterion.
