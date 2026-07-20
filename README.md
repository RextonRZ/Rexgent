<div align="center">

<img src="frontend/public/projectmedia/Rexgent.png" alt="Rexgent" width="360" />

### One line in. A finished short drama out.

Type a premise or drop in a script, and an AI crew writes it, casts it, storyboards it, films it, voices it, and cuts it into a finished episode. English or Chinese, 22 visual styles, vertical or widescreen.

**[▶ Try it live](https://rexgent.rzrexton.com)** · Built on Qwen Cloud for the Global AI Hackathon (Track 2: AI Showrunner)

</div>

---

## Why I built it

Writing the script was never the hard part. AI can already do that. The hard part is everything after: keeping one face the same across forty shots, getting the model to generate the action you actually wrote, and not burning your whole budget doing it.

So Rexgent is built around those three problems, hallucination, consistency, and cost. You bring an idea. It runs the studio.

---

## A walk through the app

**The landing page.** Real drama frames, the 22 styles, and the two ways in: a premise or your own script.
![Landing](frontend/public/projectmedia/landing.png)

**Your studio.** Every drama you have made, what each one cost, and how your account is doing, in one place.
![Dashboard](frontend/public/projectmedia/studiodashboard.png)

**Create a drama.** Pick a title, genre, one of 22 looks, a budget, and an episode count.
![Create a drama](frontend/public/projectmedia/createnewdrama.png)

**Write, or import.** Type one line and the agent writes the screenplay, or import a PDF, DOCX or Fountain. Either way it judges its own draft on 8 axes and rewrites the weak ones.
![Script editor and quality score](frontend/public/projectmedia/scripteditorpageandscriptqualityscore.png)

**Cast the production bible.** Every character gets face and per-scene costume plates locked from one reference. Upload your own photo or let the agent invent a face.
![Casting bible and costume plates](frontend/public/projectmedia/castingbiblecotumeplate.png)

**See who connects to whom.** A relationship graph, and how those bonds change as the story moves.
![Character relationship graph](frontend/public/projectmedia/characterrelationshipgraph.png)

**Storyboard with an AI Director.** Every scene broken into shots: size, angle, lens, blocking, and the 180 degree rule enforced so the cuts actually work.
![Storyboard generation](frontend/public/projectmedia/storyboardgeneration.png)

**The story map and camera plans.** A Neo4j-backed memory of everything the story has established, plus a top-down plan of exactly what each camera sees.
![Story graph and camera plan](frontend/public/projectmedia/storyrelationshipgraphandcameraplan.png)

**Render, with receipts.** Two video models, each shot sent to the one built for it, every clip scored for face and background drift.
![Video generation](frontend/public/projectmedia/videogeneration.png)

**Watch the crew work.** Every stage expands into its real tools next to a cost meter that never stops counting.
![Crew at work](frontend/public/projectmedia/crewatwork.png)

**Edit and export.** Add music, burn captions, and export. The finished episode plays in a phone frame.
![Export editor](frontend/public/projectmedia/exporteditor.png)

**Prove the spend.** The cost ledger turned into charts: routing efficiency, per-model receipts, and reliability health.
![Usage and analytics](frontend/public/projectmedia/usageanalytics.png)

---

## The 22 visual styles

Pick a look when you create the drama. It becomes a text seed that primes the style plate and every face and costume plate, so the whole production stays in that world. Photoreal is the default (no seed).

| Style | Prompt seed |
|---|---|
| Photoreal cinematic | *(default)* cinematic realistic drama |
| Pixar 3D | pixar style 3d animated feature look, expressive stylized characters, soft global illumination |
| Disney | disney style animated feature look, expressive charming characters, polished fairytale lighting |
| Ghibli | ghibli inspired hand-painted animation style, lush natural backgrounds, soft warm light |
| Anime | anime style 2D animation, clean line art, large expressive eyes, cel shading, vivid palette |
| Chibi | chibi anime style, tiny bodies with oversized heads, big eyes, cute rounded features |
| Manga | manga style monochrome illustration, ink line art, screentone shading, dramatic composition |
| Cartoon | cartoon style animated drama, bold clean outlines, flat vivid colors, exaggerated expressions |
| Cel shaded | cel-shaded animation look, hard two-tone shadows, crisp dark outlines, saturated colors |
| Flat 2D | 2d flat animation style, simple graphic shapes, bold color blocking, minimal shading |
| Comic book | comic book style, inked outlines, halftone dot shading, dynamic high-contrast panels |
| Illustrated storybook | illustrated storybook style, painterly textures, soft edges, warm picture book light |
| Hand drawn | hand-drawn animation style, visible pencil linework, organic wobble, sketchbook charm |
| Watercolor | watercolor painting style, soft bleeding washes, paper grain texture, gentle gradients |
| Sketch | sketch style, rough pencil strokes, crosshatched shading, unfinished paper drawing look |
| Claymation | claymation style, sculpted clay characters, visible fingerprint texture, handmade sets |
| Stop motion | stop-motion puppet animation style, handcrafted miniature sets, tactile fabric and wood textures |
| Pixel art | pixel art style, chunky visible pixels, limited color palette, retro game look |
| 8 bit retro | 8-bit pixel art style, blocky low resolution sprites, tiny palette, retro console look |
| 16 bit retro | 16-bit pixel art style, detailed sprites, dithered shading, golden era console look |
| Low poly 3D | low-poly 3d style, faceted geometric surfaces, flat shaded polygons, minimalist forms |
| Voxel | voxel art style, 3d cube blocks, isometric charm, chunky stepped geometry |

> Every style on the landing page is a real clip the pipeline rendered from the same scene, same character reference, same prompt. Only the style changed.

---

## How a shot gets designed

The AI Director does not point the camera at whoever is talking. It gives every shot a purpose, a size, an angle, a lens, and blocking for where each character stands. Here is the vocabulary it works in.

**Shot sizes**

| Shot | Frames |
|---|---|
| ECU · Extreme Close-Up | eyes or a detail fill the frame |
| CU · Close-Up | the face fills the frame |
| MCU · Medium Close-Up | chest up, emotion readable |
| MS · Medium Shot | waist up, gesture visible |
| FS · Full Shot | the whole body in frame |
| WS · Wide Shot | the whole space in view |
| LS · Long Shot | figure small in the environment |
| EWS · Extreme Wide Shot | establishes where we are |
| OTS · Over the Shoulder | behind one character, looking at the other |
| POV · Point of View | we see what the character sees |
| INSERT | a detail cutaway, hands or an object |

**Camera moves**

| Move | Effect |
|---|---|
| Static | locked frame, stillness |
| Dolly in / out | camera physically pushes in or pulls back |
| Pan left / right | camera swivels across the space |
| Tilt up / down | camera pivots vertically |
| Zoom in / out | the lens tightens or widens |
| Tracking | camera follows a moving subject |
| Handheld | subtle shake, documentary tension |
| Drone | sweeping aerial move |

**A real prompt it produced** (an over-the-shoulder chase, photoreal):

> Over-the-shoulder shot from an unseen pursuer's perspective: a delicate, oval-faced person with soft fair skin, long straight black hair parted centrally and adorned with subtle floral hairpins, a small mole near the left cheek, dashing urgently into a narrow cobblestone alley at night. Cool-toned moonlight casts sharp shadows; distant flickering gas lamp glows faintly. Background: weathered grey walls, a low wooden doorframe with faded red cloth curtain, broken pottery in the corner. Dolly-in motion intensifies urgency. Cinematic shallow depth of field, subject sharp, background softly blurred.

**And a reference-locked prompt** (identity pinned to plates, so the model cannot swap faces):

> Single speaker. Cinematic. Reference image guide (match each person to their OWN image, never swap faces or outfits): [Image 1] is ANGELINE (their face AND the exact outfit); [Image 2] is the scene's set, keep its furniture and props from THIS shot's camera angle; [Image 3] is the visual style. CU, 85mm lens...

---

## How it works

A LangGraph state machine runs the whole pipeline. Each stage is a real agent with real tools.

| Stage | What happens |
|---|---|
| **Develop + write** | Qwen-Max invents the dramatic spine (conflict, secret, mid-story turn), then writes cliffhanger episodes and judges its own draft on 8 axes. A rewrite that scores lower is discarded for the original. |
| **Cast** | Face and costume plates are image-edited from one locked reference, in the chosen style. Pets and creatures too, scaled to real size. Each plate is probed against the video model's own reference check before any dollar render. |
| **Storyboard** | The AI Director plans coverage, then a deterministic staging engine threads world state across the scene: positions, held objects, barriers, and absences carry shot to shot. An LLM cast audit removes anyone only talked about, not shown. |
| **Budget** | Every shot is scored for importance and routed to the model that fits it. Anything over the cap defers, lowest priority first. |
| **Render** | Reference-conditioned clips, validated by real ArcFace face matching plus a vision check. Weak takes are flagged, never silently shipped. A prompt blocked by moderation is auto-rewritten and retried. |
| **Voice + export** | HappyHorse speaks each line natively as it renders. Lines land on the exact shot, music ducks under speech, captions burn in, and each episode exports as its own video plus a season zip. |

**Two video models, split by what each shot must hold.** Anything with a face or a line renders on **HappyHorse** (locks the face from reference plates, speaks natively). Silent same-angle continuations and people-free scenery render on **Wan 2.7**. The split was decided by scored head-to-head runs on real dramas, not by guesswork.

**Consistency is engineered, not hoped for.** Locked reference plates, a deterministic staging engine, previous-frame handoff, ArcFace verification, and a Neo4j narrative memory that stops later scenes from contradicting earlier ones.

---

## Qwen Cloud integration

Rexgent runs on **17 Qwen Cloud models** over the DashScope international API, each routed to the job it does best.

- **Language:** Qwen-Max (writing), Qwen-Plus (judgment), Qwen-Flash (structuring)
- **Vision:** Qwen3-VL-Plus (continuity scoring + frame handoff), Qwen-VL-Max (reads uploaded photos)
- **Image:** Wan2.6-T2I (plates), Qwen-Image-Edit-Max (costume edits from a locked face)
- **Video:** HappyHorse 1.1 (characters + native speech), Wan 2.7 (scenery + silent continuation), HappyHorse-Video-Edit (fix a take)
- **Audio:** Qwen3-TTS (designed / preset / cloned voices), Fun-ASR and Qwen3-ASR-Flash (word-level timing, hallucinated-speech detection)

Plus a two-pass Director Engine and **7 custom MCP tools** (narrative judge, plot gap detector, ending engine, token optimizer, scene prompt craft, set dresser, consistency guard) served over the real Model Context Protocol.

---

## Getting Started

**Prerequisites:** Python 3.11+ · Node.js 20+ · Docker & Docker Compose · a [Qwen Cloud](https://www.qwencloud.com/) key (dashscope-intl) · an Alibaba Cloud OSS bucket.

**Quick start (Docker):**

```bash
git clone https://github.com/RextonRZ/Rexgent.git
cd Rexgent
cp backend/.env.example backend/.env   # add your keys
docker-compose up --build              # api + worker + frontend + postgres + redis + neo4j
```

Frontend: http://localhost:3000 · API: http://localhost:8000 · Docs: http://localhost:8000/docs

**Manual setup:**

```bash
# backend
cd backend
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:socket_app --reload --port 8000

# celery worker (separate terminal: generation / casting / export run here)
celery -A app.workers.celery_app worker --loglevel=info

# frontend
cd frontend && npm install && npm run dev
```

**Key environment variables:**

```bash
QWEN_API_KEY=your_qwen_api_key            # local-dev fallback key
REQUIRE_USER_API_KEY=false                # true on public deploys: every user pastes their own key
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
OSS_ACCESS_KEY_ID=... / OSS_ACCESS_KEY_SECRET=... / OSS_BUCKET_NAME=... / OSS_ENDPOINT=...
DATABASE_URL=postgresql://user:password@localhost:5432/rexgent
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your_secret_key                # also encrypts stored user API keys
```

---

## Deploy (Alibaba Cloud ECS)

One instance runs everything via the production compose base (the dev overlay is local only):

```bash
# Ubuntu 22.04 ECS, >= 2 vCPU / 8 GB, ports 3000 + 8000 open
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
git clone https://github.com/RextonRZ/Rexgent.git && cd Rexgent
# copy your backend/.env onto the server (scp), never commit it

export PUBLIC_API_URL="http://<server-ip>:8000"      # baked into the frontend build
export FRONTEND_ORIGIN="http://<server-ip>:3000"     # added to CORS (HTTP + websocket)
docker compose -f docker-compose.yml up -d --build
```

Migrations run automatically on backend start. **On a public deploy set `REQUIRE_USER_API_KEY=true`** so every visitor bills their own Qwen Cloud account.

**With a domain**, point two A records (`@` and `api`) at the ECS IP and let Caddy handle HTTPS:

```bash
sudo apt install -y caddy
# /etc/caddy/Caddyfile
#   yourdomain.com     { reverse_proxy localhost:3000 }
#   api.yourdomain.com { reverse_proxy localhost:8000 }
sudo systemctl reload caddy

export PUBLIC_API_URL="https://api.yourdomain.com"
export FRONTEND_ORIGIN="https://yourdomain.com"
docker compose -f docker-compose.yml up -d --build   # rebuild: the API URL is baked into the frontend
```

```mermaid
flowchart LR
    U([Browser])
    subgraph ECS["Alibaba Cloud ECS — docker compose"]
        FE2["frontend :3000<br/>Next.js"]
        BE["backend :8000<br/>FastAPI + Socket.IO"]
        WK2["worker<br/>Celery ×2 + ffmpeg"]
        RD2[("Redis 7")]
        DB[("PostgreSQL 16<br/>pgvector")]
        N4[("Neo4j 5")]
    end
    DS["Qwen Cloud<br/>DashScope intl — 17 models"]
    OSS2[("Alibaba OSS<br/>plates · clips · episodes")]

    U --> FE2
    U -- "REST + WebSocket" --> BE
    BE <--> RD2
    RD2 <--> WK2
    BE --> DB & N4
    WK2 --> DB
    BE -- "LLM / VL" --> DS
    WK2 -- "video · image" --> DS
    WK2 -- "persist media" --> OSS2
```

**MCP server:** the 7 tools are also served over the real Model Context Protocol (official Python SDK, stdio), so any MCP client can discover and call them:

```bash
cd backend
python -m venv .venv-mcp && .venv-mcp/Scripts/activate
pip install -r mcp_requirements.txt
python mcp_server_entry.py
```

---

## Tech stack

**Frontend:** Next.js 14, React, TypeScript, Tailwind CSS, D3, Socket.IO client, Zustand, React Query.
**Backend:** FastAPI, Celery, Socket.IO, LangGraph, SQLAlchemy, FFmpeg.
**Data:** PostgreSQL + pgvector (ArcFace face embeddings via InsightFace), Redis, Neo4j.
**Cloud:** Qwen Cloud (DashScope), Alibaba Cloud OSS + ECS, Docker Compose.

---

## License

MIT
