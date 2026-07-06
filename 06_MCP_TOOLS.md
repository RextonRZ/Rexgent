> **Historical design doc** from the original build plan — kept for provenance. The shipped architecture (LangGraph agent, model tiering, production bible, set dresser, budget fitting, 9:16 export) is described in [README.md](README.md) and [SUBMISSION.md](SUBMISSION.md).

# Rexgent — MCP Tools Specification

6 custom MCP tools that form the AI intelligence layer of Rexgent. Each is a distinct engineering contribution, not a wrapper around an existing API.

---

## 1. ScenePromptCraft

**Purpose:** Converts storyboard shot data into optimised cinematic prompts for Wan and HappyHorse. The innovation is the prompt DSL — a structured intermediate representation that enforces cinematography rules before prompt text is generated.

**Input schema:**
```json
{
  "shot": {
    "shot_type": "CU",
    "camera_movement": "STATIC",
    "characters_in_frame": ["Detective Yuki"],
    "action": "She turns slowly to face the camera",
    "lighting": "DRAMATIC_SIDE",
    "colour_mood": "DESATURATED",
    "emotional_beat": "cold realisation",
    "estimated_duration_seconds": 5
  },
  "character_visuals": {
    "Detective Yuki": {
      "video_prompt_fragment": "young East Asian woman, sharp cheekbones, short black hair, leather jacket, silver earring",
      "face_keywords": ["sharp cheekbones", "almond eyes", "strong jaw"]
    }
  },
  "target_model": "wan",
  "style_bible": {
    "colour_grade": "neo-noir",
    "overall_mood": "tense thriller",
    "cinematographer_reference": "Roger Deakins"
  }
}
```

**Output schema:**
```json
{
  "prompt": "Close-up, static camera, young East Asian woman with sharp cheekbones and short black hair in a leather jacket, turns slowly to face camera with cold expression, dramatic side lighting casting half her face in shadow, desaturated blue-grey tones, tense ambient silence, 5s",
  "negative_prompt": "blurry, distorted face, multiple people, oversaturated, shaky camera, cartoon, anime",
  "model_parameters": {
    "resolution": "1080p",
    "duration": 5,
    "audio_mode": "auto",
    "aspect_ratio": "16:9"
  },
  "prompt_word_count": 47
}
```

**Key logic:**
```python
class ScenePromptCraft:
    SHOT_TYPE_VOCABULARY = {
        "ECU": "extreme close-up",
        "CU": "close-up",
        "MCU": "medium close-up",
        "MS": "medium shot",
        "FS": "full shot",
        "LS": "long shot",
        "EWS": "extreme wide establishing shot",
        "POV": "point-of-view shot",
        "OTS": "over-the-shoulder shot",
    }
    
    LIGHTING_VOCABULARY = {
        "DRAMATIC_SIDE": "dramatic side lighting casting half the face in shadow",
        "GOLDEN_HOUR": "warm golden hour sunlight from low angle",
        "NATURAL": "soft natural diffused daylight",
        "NEON": "neon light reflections in rain-slicked surfaces",
        # ...
    }
    
    def build_prompt(self, shot, character_visuals, style_bible) -> str:
        # 1. Start with shot type
        # 2. Add camera movement
        # 3. Replace character names with visual descriptions
        # 4. Describe action
        # 5. Add lighting
        # 6. Add colour mood
        # 7. Add audio suggestion
        # 8. End with duration
        # 9. Enforce 80-word limit via Qwen-Max refinement if exceeded
```

---

## 2. ConsistencyGuard

**Purpose:** Validates that generated video clips contain characters who visually match their established reference in the character bible. Solves the #1 problem in AI video — character drift between scenes.

**Input schema:**
```json
{
  "clip_url": "https://oss.rexgent.ai/clips/clip_007.mp4",
  "expected_characters": [
    {
      "name": "Detective Yuki",
      "face_embedding": [0.23, -0.14, 0.87, ...],
      "face_keywords": ["sharp cheekbones", "almond eyes", "short black hair"],
      "reference_image_url": "https://oss.rexgent.ai/characters/yuki/reference.jpg"
    }
  ],
  "sample_frame_count": 3,
  "similarity_threshold": 0.75
}
```

**Output schema:**
```json
{
  "overall_pass": true,
  "overall_similarity": 0.88,
  "character_results": [
    {
      "character_name": "Detective Yuki",
      "detected": true,
      "similarity_score": 0.88,
      "pass": true,
      "frame_scores": [0.91, 0.85, 0.88],
      "failure_reason": null
    }
  ],
  "recommendation": "APPROVE|RETRY_SAME_PROMPT|RETRY_STRONGER_FACE|MANUAL_REVIEW",
  "retry_instruction": null
}
```

**Key logic:**
```python
class ConsistencyGuard:
    def validate(self, clip_url, expected_characters, threshold=0.75):
        # 1. Download clip from OSS
        # 2. Sample N frames (evenly spaced)
        # 3. For each frame:
        #    a. Call Qwen-VL to detect faces and extract embeddings
        #    b. Match detected faces to expected characters by embedding similarity
        #    c. Compute cosine similarity against stored character embedding
        # 4. Average similarity across frames per character
        # 5. If any character below threshold → determine retry strategy:
        #    - Score 0.6–0.74: RETRY_STRONGER_FACE (add more face keywords)
        #    - Score 0.4–0.59: RETRY_SAME_PROMPT (bad generation, reseed)
        #    - Score < 0.4: MANUAL_REVIEW (embedding mismatch, possible wrong character)
        
    def get_retry_instruction(self, character, score) -> str:
        if score < 0.6:
            return f"Emphasise: {', '.join(character.face_keywords)}. Use subject reference image."
        return "Reseed generation with different random seed."
```

**Qwen-VL call:**
```python
async def extract_face_embedding(self, image_url: str) -> list[float]:
    response = await qwen_vl_client.chat(
        model="qwen-vl-max",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": "Describe the face of the main person in this image in detail. Include: facial structure, eye shape, nose shape, jawline, skin tone, distinctive features. Return as JSON with keys: face_description, distinctive_features, embedding_keywords"}
            ]
        }]
    )
    # Extract structured face description + compute embedding from VL output
```

---

## 3. TokenOptimizer

**Purpose:** Scores every scene by emotional importance and allocates the video generation budget to maximise quality where it matters most. Turns the token budget constraint into a design feature.

**Input schema:**
```json
{
  "shots": [
    {
      "shot_id": "shot_001",
      "scene_number": 1,
      "shot_type": "EWS",
      "emotional_beat": "establishing dread",
      "action": "Empty rain-soaked street, distant neon signs",
      "dialogue": null,
      "estimated_duration_seconds": 4,
      "characters_in_frame": []
    }
  ],
  "budget_usd": 40.00,
  "wan_cost_per_sec": 0.07,
  "happyhorse_cost_per_sec": 0.05,
  "reserve_pct": 0.15
}
```

**Output schema:**
```json
{
  "total_shots": 12,
  "total_estimated_seconds": 68,
  "budget_available": 34.00,
  "budget_reserved": 6.00,
  "scored_shots": [
    {
      "shot_id": "shot_001",
      "importance_score": 3,
      "quality_tier": "happyhorse",
      "model": "happyhorse-1.1-t2v",
      "estimated_cost_usd": 0.20,
      "reasoning": "Establishing shot — visual quality less critical than key character scenes"
    }
  ],
  "wan_shots": 4,
  "happyhorse_shots": 8,
  "total_estimated_cost": 3.24,
  "budget_remaining": 30.76,
  "optimisation_summary": "4 key emotional scenes allocated to Wan 2.7 for maximum quality. 8 transitional and supporting scenes use HappyHorse 1.1."
}
```

**Scoring algorithm:**
```python
def score_shot(self, shot: Shot) -> int:
    score = 0
    
    # Climax indicators
    if any(word in shot.emotional_beat.lower() for word in 
           ["climax", "revelation", "confrontation", "betrayal", "breaking point"]):
        score += 3
    
    # Character presence
    if len(shot.characters_in_frame) >= 2:
        score += 1
    if len(shot.characters_in_frame) >= 1:
        score += 1
    
    # Dialogue = face visibility matters
    if shot.dialogue:
        score += 2
    
    # Shot type weighting
    shot_weights = {"CU": 2, "ECU": 2, "MCU": 1, "MS": 1, "LS": 0, "EWS": 0}
    score += shot_weights.get(shot.shot_type, 0)
    
    # Duration (longer = more expensive = needs more justification)
    if shot.estimated_duration_seconds >= 10:
        score += 1
    
    return min(score, 10)
```

---

## 4. NarrativeJudge

**Purpose:** A second Qwen-Max call that acts as a critic (not the author) to evaluate script quality before any tokens are spent on video generation. Prevents bad scripts from becoming expensive bad videos.

**Input schema:**
```json
{
  "script": { ... },
  "blocking_threshold": 5.0,
  "axes": ["tension_arc", "character_consistency", "pacing", "dialogue_naturalness", "genre_adherence"]
}
```

**Output schema:**
```json
{
  "scores": {
    "tension_arc": 7.5,
    "character_consistency": 8.0,
    "pacing": 6.5,
    "dialogue_naturalness": 7.0,
    "genre_adherence": 8.5
  },
  "overall": 7.5,
  "blocking_issues": [],
  "top_strengths": [
    "Strong atmospheric tension in the opening act",
    "Distinct character voices — each character sounds unique"
  ],
  "top_weaknesses": [
    "Scene 4 pacing drags — the exposition could be compressed",
    "The antagonist's motivation is underdeveloped"
  ],
  "recommendation": "PROCEED",
  "judge_summary": "Solid genre thriller with strong visual potential. Proceed to production with minor pacing note for Scene 4."
}
```

**Blocking logic:**
```python
def evaluate(self, script, blocking_threshold=5.0):
    judgement = self._call_qwen_max_as_judge(script)
    
    # Hard block: any single axis below threshold
    for axis, score in judgement.scores.items():
        if score < blocking_threshold:
            judgement.blocking_issues.append(
                f"{axis} score ({score}) is below minimum threshold ({blocking_threshold}). Rewrite required."
            )
    
    # Auto-set recommendation based on blocking issues
    if judgement.blocking_issues:
        judgement.recommendation = "REVISE_FIRST"
    elif judgement.overall < 6.0:
        judgement.recommendation = "MAJOR_REWRITE"
    else:
        judgement.recommendation = "PROCEED"
    
    return judgement
```

---

## 5. PlotGapDetector

**Purpose:** Reads the full structured script and returns a typed array of narrative problems. Acts as an AI script editor that catches issues a first-time writer would miss.

**Input schema:**
```json
{
  "script": { ... },
  "sensitivity": "STRICT|NORMAL|LENIENT",
  "ignore_types": []
}
```

**Output schema:**
```json
{
  "total_flags": 3,
  "critical_count": 0,
  "major_count": 2,
  "minor_count": 1,
  "flags": [
    {
      "flag_id": "flag_001",
      "flag_type": "MISSING_MOTIVATION",
      "severity": "MAJOR",
      "scene_number": 3,
      "description": "Detective Yuki shoots the AI without any established reason to distrust it at this point in the story",
      "evidence": "Scene 3, line 12: 'YUKI shoots the drone without hesitation'",
      "suggestion": "Add a scene or moment earlier where Yuki discovers something suspicious about the AI's behaviour",
      "status": "OPEN"
    }
  ]
}
```

**Flag status lifecycle:**
```
OPEN → ACKNOWLEDGED (user saw it) → FIXED (user edited script) → DISMISSED (user ignored it)
```

---

## 6. EndingEngine

**Purpose:** Checks whether the screenplay has a complete, satisfying ending. If not, generates branching alternative endings as a structured graph the user can explore and select from.

**Input schema:**
```json
{
  "script": { ... },
  "generate_alternatives": true,
  "num_alternatives": 3,
  "tone_preferences": ["BITTERSWEET", "HOPEFUL"]
}
```

**Output schema:**
```json
{
  "has_complete_ending": false,
  "ending_quality": "PARTIAL",
  "analysis": {
    "main_conflict_resolved": false,
    "protagonist_arc_complete": true,
    "emotional_payoff": "WEAK",
    "open_threads": [
      "The origin of the AI partner is never explained",
      "Yuki's relationship with her estranged family is set up in Act 1 but never resolved"
    ]
  },
  "current_ending_summary": "Story ends mid-confrontation without resolution",
  "alternatives": [
    {
      "id": "ending_a",
      "title": "The sacrifice",
      "summary": "The AI partner sacrifices itself to save Yuki, revealing it has developed genuine emotions. Yuki escapes but is left questioning what it means to be human. Bittersweet but complete.",
      "emotional_tone": "BITTERSWEET",
      "resolves_main_conflict": true,
      "resolves_family_thread": false,
      "compatibility_score": 9.2,
      "new_scenes_needed": 1,
      "estimated_additional_duration": "3 minutes"
    },
    {
      "id": "ending_b",
      "title": "The reveal",
      "summary": "Yuki discovers she too is an AI — she was created as a control experiment. The corporation is exposed. Both AIs escape together. Twist ending.",
      "emotional_tone": "AMBIGUOUS",
      "resolves_main_conflict": true,
      "resolves_family_thread": false,
      "compatibility_score": 7.1,
      "new_scenes_needed": 2,
      "estimated_additional_duration": "5 minutes"
    },
    {
      "id": "ending_c",
      "title": "The compromise",
      "summary": "Yuki lets the AI go in exchange for the evidence she needs. Neither fully wins. She returns home to her family — the AI's influence softened her. Quiet resolution.",
      "emotional_tone": "HOPEFUL",
      "resolves_main_conflict": true,
      "resolves_family_thread": true,
      "compatibility_score": 8.8,
      "new_scenes_needed": 2,
      "estimated_additional_duration": "4 minutes"
    }
  ]
}
```

**Graph rendering:**
The `alternatives` array is rendered as a D3 force graph in the frontend:
- Central node: current story state
- Three branch nodes: each alternative ending
- Edge labels: compatibility score
- Node colour: emotional tone (bittersweet = amber, hopeful = teal, ambiguous = purple)
- Click on node: expands to show full summary + "Use this ending" button

---

## MCP Tool Server Setup

All 6 tools are served as a FastAPI microservice:

```python
# backend/app/mcp_tools/__init__.py
from fastapi import FastAPI
from .scene_prompt_craft import router as spc_router
from .consistency_guard import router as cg_router
from .token_optimizer import router as to_router
from .narrative_judge import router as nj_router
from .plot_gap_detector import router as pgd_router
from .ending_engine import router as ee_router

mcp_app = FastAPI(title="Rexgent MCP Tools")
mcp_app.include_router(spc_router, prefix="/tools/scene-prompt-craft")
mcp_app.include_router(cg_router, prefix="/tools/consistency-guard")
mcp_app.include_router(to_router, prefix="/tools/token-optimizer")
mcp_app.include_router(nj_router, prefix="/tools/narrative-judge")
mcp_app.include_router(pgd_router, prefix="/tools/plot-gap-detector")
mcp_app.include_router(ee_router, prefix="/tools/ending-engine")
```

Each tool is also registered in the Orchestrator's tool registry so Qwen-Max can call them as function tools:

```python
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "scene_prompt_craft",
            "description": "Build optimised video generation prompt from shot data",
            "parameters": { ... }  # JSON Schema matching input schema above
        }
    },
    # ... repeat for all 6 tools
]
```
