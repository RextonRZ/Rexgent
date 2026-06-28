# ShowMind — Narrative Memory Graph

The Narrative Memory Graph (NMG) is the central shared state that makes ShowMind coherent across all pipeline stages. Without it, each AI call is stateless — the storyboard generator doesn't know what the script analyser found, the video prompt builder doesn't know what the character extractor established. The NMG is what makes ShowMind an *agent*, not a collection of API calls.

---

## Design Philosophy

Every AI system that generates multi-part content faces the same problem: **context window limits force amnesia between calls**. A 120-page script can't fit in a single Qwen-Max context. Even if it could, you'd be re-processing the whole thing for every call.

The NMG solves this by extracting and structuring the *essential facts* from each stage and storing them in a compact, queryable format. Each new AI call gets only the relevant slice of the graph injected into its context — not the entire history.

---

## Data Structure

```python
@dataclass
class NarrativeMemoryGraph:
    project_id: str
    version: int                              # increments on every write
    last_updated: datetime
    
    # ─── Characters ───────────────────────────────────────────────
    characters: dict[str, CharacterState]
    # Key: character name (normalised lowercase)
    # Value: full character state at every scene
    
    # ─── Established facts ────────────────────────────────────────
    facts: list[NarrativeFact]
    # All facts extracted from script. Used to prevent contradictions
    # in storyboard and video prompts.
    
    # ─── Visual motifs ────────────────────────────────────────────
    motifs: list[VisualMotif]
    # Recurring visual elements established in early scenes.
    # Injected into later scene prompts for visual consistency.
    
    # ─── Tension curve ────────────────────────────────────────────
    tension_curve: list[TensionPoint]
    # Emotional intensity at each scene (0–10).
    # Used by TokenOptimizer to identify climax scenes.
    
    # ─── Prompt history ───────────────────────────────────────────
    prompt_history: list[PromptRecord]
    # Every video generation prompt ever created.
    # Used by regen rewriter to understand what was tried before.
    
    # ─── Relationship graph ───────────────────────────────────────
    relationships: list[CharacterRelationship]
    # Extracted from script. Read by storyboard generator for
    # blocking decisions (who stands where, who faces whom).
    
    # ─── Plot flags ───────────────────────────────────────────────
    open_flags: list[PlotFlag]
    # Unresolved issues from PlotGapDetector.
    # Injected as warnings into any AI call that touches flagged scenes.
```

---

## Sub-types

```python
@dataclass
class CharacterState:
    name: str
    role: str
    mbti: str
    face_embedding: list[float]          # Qwen-VL extracted
    visual_description: str             # Used in every prompt this character appears in
    reference_image_url: str | None
    
    # State per scene (for arc tracking)
    scene_states: dict[int, SceneCharacterState]
    # Key: scene number
    # Value: emotional state, physical location, relationship status
    
    # Cumulative appearance description (updated as scenes are generated)
    established_appearance_notes: list[str]

@dataclass  
class SceneCharacterState:
    scene_number: int
    emotional_state: str                # e.g. "guarded, suspicious"
    physical_location: str
    knows_about: list[str]             # what this character knows at this point
    relationship_states: dict[str, str] # other_char_name → current relationship status

@dataclass
class NarrativeFact:
    fact_id: str
    scene_number: int
    category: str                      # LOCATION|CHARACTER|OBJECT|RULE|RELATIONSHIP
    fact: str                          # e.g. "The AI partner's name is ARIA"
    established_by: str                # e.g. "dialogue" | "stage direction" | "inference"
    contradicted_by: str | None        # if a later scene contradicts this

@dataclass
class VisualMotif:
    motif_id: str
    name: str                          # e.g. "rain-slicked streets"
    description: str                   # detailed visual description
    first_scene: int
    scenes_present: list[int]
    prompt_fragment: str               # ready-to-inject text for video prompts

@dataclass
class TensionPoint:
    scene_number: int
    tension_score: float               # 0–10
    beat_type: str                     # SETUP|RISING|MIDPOINT|CLIMAX|FALLING|RESOLUTION
    reasoning: str

@dataclass
class PromptRecord:
    shot_id: str
    scene_number: int
    prompt: str
    model_used: str
    output_url: str | None
    consistency_score: float | None
    retries: int
    final_status: str                  # APPROVED|FAILED|MANUAL_REVIEW
```

---

## Read Patterns

Each AI service queries the NMG for only what it needs:

```python
class NarrativeMemoryGraph:
    
    def get_character_context(self, character_name: str, scene_number: int) -> str:
        """
        Returns a compact context string for injecting into a video prompt.
        Includes: visual description, emotional state at this scene, 
        known facts relevant to this scene.
        
        Example output:
        "Young East Asian detective, sharp cheekbones, short black hair, leather jacket.
         At this point in the story: guarded and suspicious, does not yet know ARIA is AI.
         Key visual fact: always has silver earring in left ear."
        """
    
    def get_established_facts(self, scene_number: int, categories: list[str] = None) -> list[str]:
        """
        Returns all facts established before this scene number.
        Optionally filtered by category.
        Used by: storyboard generator, prompt crafter, regen rewriter.
        """
    
    def get_visual_motifs_for_scene(self, scene_number: int) -> list[str]:
        """
        Returns prompt fragments for motifs that should appear in this scene.
        """
    
    def get_tension_at_scene(self, scene_number: int) -> TensionPoint:
        """
        Returns tension level and beat type for a given scene.
        Used by: TokenOptimizer (scoring), storyboard generator (shot intensity).
        """
    
    def check_contradiction(self, proposed_fact: str, scene_number: int) -> bool:
        """
        Returns True if proposed_fact contradicts any established fact.
        Used by: script generator (when AI writes from scratch) to avoid self-contradiction.
        """
    
    def get_open_flags_for_scene(self, scene_number: int) -> list[PlotFlag]:
        """
        Returns unresolved PlotFlags for this scene.
        Injected as warning context into any AI call touching this scene.
        """
    
    def get_prompt_history_for_shot(self, shot_id: str) -> list[PromptRecord]:
        """
        Returns all previous prompt attempts for a shot.
        Used by: regen rewriter to avoid repeating failed approaches.
        """
```

---

## Write Patterns

```python
class NarrativeMemoryGraph:
    
    def register_character(self, character: Character) -> None:
        """Called by character extractor after parsing."""
    
    def update_character_state(self, character_name: str, scene_number: int, state: SceneCharacterState) -> None:
        """Called by storyboard generator as it processes each scene."""
    
    def record_fact(self, fact: NarrativeFact) -> None:
        """Called by script analyser for every extractable fact."""
    
    def register_motif(self, motif: VisualMotif) -> None:
        """Called by storyboard generator when it identifies recurring visual elements."""
    
    def set_tension_curve(self, tension_points: list[TensionPoint]) -> None:
        """Called by NarrativeJudge after script scoring."""
    
    def record_prompt(self, record: PromptRecord) -> None:
        """Called by generation runner after every clip attempt."""
    
    def resolve_flag(self, flag_id: str, resolution: str) -> None:
        """Called when user fixes or dismisses a PlotFlag."""
```

---

## Persistence

The NMG is serialised as JSON and stored in two places:

**Redis (hot cache):** Full NMG for the active project. Sub-5ms read access for the orchestrator.
```
Key: nmg:{project_id}
TTL: 2 hours after last access
Value: NMG serialised to JSON
```

**PostgreSQL (cold storage):** Versioned snapshots at each major pipeline stage.
```sql
CREATE TABLE narrative_memory_snapshots (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    version INTEGER,
    stage VARCHAR(50),  -- 'after_script' | 'after_characters' | 'after_storyboard' | 'after_generation'
    graph_json JSONB,
    created_at TIMESTAMP
);
```

Versioning enables rollback: if a user wants to redo the storyboard from scratch, the orchestrator can reload the `after_characters` snapshot.

---

## How the NMG Makes Video Better

Concrete example of what the NMG prevents:

**Without NMG:**
- Scene 1 prompt: "...a detective with long brown hair..."
- Scene 5 prompt (different API call, different context): "...the investigator with short blonde hair..."
- Result: same character looks like two different people

**With NMG:**
- Character extraction stores: `"Detective Yuki: short black hair, leather jacket, silver earring"`
- ScenePromptCraft queries NMG before building every prompt
- Both Scene 1 and Scene 5 get the exact same visual description injected
- ConsistencyGuard verifies the face matches the stored embedding
- Result: consistent character across all clips
