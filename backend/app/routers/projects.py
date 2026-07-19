import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import get_current_user
from app.models.project import Project
from app.models.user import User
from app.models.cost_event import CostEvent
from app.models.generation_job import GenerationJob
from app.models.generated_clip import GeneratedClip
from app.schemas.project import (
    BudgetEstimateRequest,
    PosterFromClipRequest,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    TitleSuggestRequest,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])

# Clips run ~5s each; GeneratedClip doesn't store duration, so the dashboard
# stats estimate film time from the clip count.
CLIP_SECONDS = 5


def _get_owned_project(project_id: str, db: Session, user: User) -> Project:
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not authorized for this project")
    return project


@router.post("", response_model=ProjectResponse)
async def create_project(
    request: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = Project(
        user_id=str(current_user.id),
        title=request.title,
        genre=request.genre,
        premise=request.premise,
    )
    if request.credit_budget is not None:
        project.credit_budget = max(1.0, float(request.credit_budget))
    if request.token_budget is not None:
        project.token_budget = max(0, int(request.token_budget))
    if request.video_ratio in ("9:16", "16:9"):
        project.video_ratio = request.video_ratio
    if request.episode_count is not None:
        project.episode_count = max(1, int(request.episode_count))
    if request.target_length is not None:
        project.target_length = max(10, int(request.target_length))
    # only known catalog keys are stored; anything else stays photoreal (NULL)
    from app.services.style_catalog import catalog_key
    project.visual_style = catalog_key(request.visual_style)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/estimate_budget")
async def estimate_project_budget(
    request: BudgetEstimateRequest,
    current_user: User = Depends(get_current_user),
):
    """Projected tokens + $ for a drama of this scope — powers the live budget
    panel in the create flow."""
    from app.services.budget_estimator import estimate_budget

    return estimate_budget(
        request.episode_count, request.target_length, request.characters
    )


@router.get("")
async def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects = (
        db.query(Project)
        .filter(Project.user_id == str(current_user.id))
        .order_by(Project.created_at.desc())
        .all()
    )
    return {"projects": [ProjectResponse.model_validate(p) for p in projects]}


@router.get("/overview")
async def projects_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Everything the dashboard needs in one call: projects with poster,
    clip stats and spend, the most recent playable clips for the recap
    shelf montage, and studio-wide totals."""
    # local import: generation router imports models we also use; the helper
    # lives there next to the clip routes it protects
    from app.routers.generation import _url_expired

    projects = (
        db.query(Project)
        .filter(Project.user_id == str(current_user.id))
        .order_by(Project.updated_at.desc())
        .all()
    )
    ids = [p.id for p in projects]

    spent_by_project: dict = {}
    clips_by_project: dict = {}
    generating: set = set()
    recent_clips: list = []

    if ids:
        for pid, total in (
            db.query(CostEvent.project_id, func.sum(CostEvent.amount_usd))
            .filter(CostEvent.project_id.in_(ids))
            .group_by(CostEvent.project_id)
            .all()
        ):
            spent_by_project[pid] = round(float(total or 0), 2)

        jobs = (
            db.query(GenerationJob)
            .filter(GenerationJob.project_id.in_(ids))
            .all()
        )
        job_project = {j.id: j.project_id for j in jobs}
        generating = {
            j.project_id for j in jobs if (j.status or "") in ("PENDING", "RUNNING")
        }

        if jobs:
            rows = (
                db.query(GeneratedClip)
                .filter(
                    GeneratedClip.job_id.in_(list(job_project.keys())),
                    GeneratedClip.url.isnot(None),
                )
                .order_by(GeneratedClip.created_at.desc())
                .all()
            )
            for c in rows:
                if _url_expired(c.url):
                    continue
                pid = job_project.get(c.job_id)
                if pid is None:
                    continue
                clips_by_project.setdefault(pid, []).append(c.url)

    title_by_id = {p.id: p.title for p in projects}
    for pid, urls in clips_by_project.items():
        for url in urls[:2]:  # at most 2 per drama so one project can't hog the shelf
            recent_clips.append(
                {"url": url, "project_id": str(pid), "project_title": title_by_id[pid]}
            )
    recent_clips = recent_clips[:6]

    total_clips = sum(len(v) for v in clips_by_project.values())
    out_projects = []
    for p in projects:
        urls = clips_by_project.get(p.id, [])
        out_projects.append(
            {
                **ProjectResponse.model_validate(p).model_dump(mode="json"),
                "clip_count": len(urls),
                "preview_clip_url": urls[0] if urls else None,
                "spent_usd": spent_by_project.get(p.id, 0.0),
                "is_generating": p.id in generating,
            }
        )

    return {
        "projects": out_projects,
        "recent_clips": recent_clips,
        "totals": {
            "dramas": len(projects),
            "clips": total_clips,
            "film_seconds": total_clips * CLIP_SECONDS,
            "spent_usd": round(sum(spent_by_project.values()), 2),
        },
    }


def _clean_title(raw: str) -> str:
    title = (raw or "").strip().splitlines()[0].strip().strip('"“”\'')
    words = title.split()
    if len(words) > 8:  # runaway response guard
        title = " ".join(words[:8])
    return title[:60]


async def _llm_title(premise: str) -> str:
    """Ask qwen for a short evocative series title. Wrapped so tests can
    patch it without a live API key."""
    from app.config import get_settings
    from app.services.qwen_client import QwenClient

    qwen = QwenClient(get_settings())
    return await qwen.chat(
        [
            {
                "role": "user",
                "content": (
                    "Suggest a title for a short drama series with this premise:\n"
                    f"{premise}\n\n"
                    "Rules: at most 5 words, evocative, Title Case, no quotes, "
                    "no punctuation at the end. Reply with the title only."
                ),
            }
        ],
        temperature=0.8,
        max_tokens=32,
        task="title",
    )


@router.post("/suggest_title")
async def suggest_title(
    request: TitleSuggestRequest,
    current_user: User = Depends(get_current_user),
):
    """One evocative title from a premise — used when creating a drama and
    by the clean-up-titles affordance on the dashboard."""
    premise = request.premise.strip()
    if not premise:
        raise HTTPException(status_code=422, detail="Premise is empty")
    try:
        title = _clean_title(await _llm_title(premise))
    except Exception:
        raise HTTPException(status_code=502, detail="Could not suggest a title")
    if not title:
        raise HTTPException(status_code=502, detail="Could not suggest a title")
    return {"title": title}


@router.get("/stats")
async def studio_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Studio stats drawer: daily generation activity for the heatmap,
    per-agent report breakdown, cost split by category, and totals.
    Aggregation happens in python — the row counts are tiny."""
    from app.models.agent_report import AgentReport

    projects = (
        db.query(Project)
        .filter(Project.user_id == str(current_user.id))
        .all()
    )
    ids = [p.id for p in projects]
    cutoff = datetime.utcnow() - timedelta(weeks=26)

    days: dict[str, dict] = {}
    total_clips = 0
    if ids:
        jobs = db.query(GenerationJob).filter(GenerationJob.project_id.in_(ids)).all()
        job_ids = [j.id for j in jobs]
        if job_ids:
            clip_rows = (
                db.query(GeneratedClip)
                .filter(
                    GeneratedClip.job_id.in_(job_ids),
                    GeneratedClip.url.isnot(None),
                )
                .all()
            )
            total_clips = len(clip_rows)
            for c in clip_rows:
                if c.created_at and c.created_at >= cutoff:
                    key = c.created_at.date().isoformat()
                    d = days.setdefault(key, {"clips": 0, "spent": 0.0})
                    d["clips"] += 1

    cost_split = {"llm": 0.0, "image": 0.0, "video": 0.0, "tts": 0.0}
    total_spent = 0.0
    if ids:
        for e in db.query(CostEvent).filter(CostEvent.project_id.in_(ids)).all():
            amount = float(e.amount_usd or 0)
            total_spent += amount
            if e.category in cost_split:
                cost_split[e.category] += amount
            if e.created_at and e.created_at >= cutoff:
                key = e.created_at.date().isoformat()
                d = days.setdefault(key, {"clips": 0, "spent": 0.0})
                d["spent"] += amount

    agents: dict[str, dict] = {}
    if ids:
        for r in (
            db.query(AgentReport).filter(AgentReport.project_id.in_(ids)).all()
        ):
            a = agents.setdefault(
                r.agent,
                {
                    "runs": 0,
                    "conf_sum": 0.0,
                    "conf_n": 0,
                    "projects": set(),
                    "last_run": None,
                },
            )
            a["runs"] += 1
            a["projects"].add(r.project_id)
            if r.created_at is not None and (
                a["last_run"] is None or r.created_at > a["last_run"]
            ):
                a["last_run"] = r.created_at
            if r.confidence is not None:
                a["conf_sum"] += float(r.confidence)
                a["conf_n"] += 1

    return {
        "days": [
            {"date": k, "clips": v["clips"], "spent": round(v["spent"], 2)}
            for k, v in sorted(days.items())
        ],
        "agents": [
            {
                "agent": name,
                "runs": a["runs"],
                "avg_confidence": round(a["conf_sum"] / a["conf_n"], 3)
                if a["conf_n"]
                else None,
                "dramas": len(a["projects"]),
                "last_run": a["last_run"].isoformat() if a["last_run"] else None,
            }
            for name, a in sorted(agents.items())
        ],
        "cost_split": {k: round(v, 2) for k, v in cost_split.items()},
        "totals": {
            "dramas": len(projects),
            "clips": total_clips,
            "film_seconds": total_clips * CLIP_SECONDS,
            "spent_usd": round(total_spent, 2),
        },
    }


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_owned_project(project_id, db, current_user)
    changes = request.model_dump(exclude_unset=True)
    if "credit_budget" in changes and changes["credit_budget"] is not None:
        changes["credit_budget"] = max(1.0, float(changes["credit_budget"]))
    if "video_ratio" in changes and changes["video_ratio"] not in ("9:16", "16:9"):
        changes.pop("video_ratio")  # ignore anything but the two valid formats
    if "episode_count" in changes and changes["episode_count"] is not None:
        changes["episode_count"] = max(1, int(changes["episode_count"]))
    if "target_length" in changes and changes["target_length"] is not None:
        changes["target_length"] = max(10, int(changes["target_length"]))
    if "visual_style" in changes:
        # canonical catalog key or NULL — "photoreal" (or junk) clears the look
        from app.services.style_catalog import catalog_key
        changes["visual_style"] = catalog_key(changes["visual_style"])
    for field, value in changes.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}/progress")
def project_progress(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Which pipeline stages have real artifacts — drives the step nav, so
    done means done (data exists), not merely visited."""
    project = _get_owned_project(project_id, db, current_user)
    from app.services.pipeline_progress import stage_progress, stale_stages
    # "stale" marks a done stage stranded on an OLDER upstream (script was
    # rewritten after casting, storyboard redone after clips) — still watchable,
    # but it should be re-run before moving on
    return {**stage_progress(db, project.id),
            "stale": stale_stages(db, project.id)}


@router.post("/{project_id}/duplicate", response_model=ProjectResponse)
async def duplicate_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Shallow duplicate: same premise/genre, fresh pipeline. Scripts, cast
    and clips are not cloned — the copy starts at the Script step."""
    source = _get_owned_project(project_id, db, current_user)
    copy = Project(
        user_id=str(current_user.id),
        title=f"{source.title} (copy)",
        genre=source.genre,
        premise=source.premise,
        episode_count=source.episode_count,
        target_length=source.target_length,
        visual_style=getattr(source, "visual_style", None),
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return copy


@router.post("/{project_id}/poster/from_clip")
async def set_poster_from_clip(
    project_id: str,
    request: PosterFromClipRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Server-side poster capture: extract the chosen frame with ffmpeg and
    host it on our OSS. The browser cannot do this itself — OSS serves clips
    without CORS headers, so a client canvas capture would be tainted."""
    from app.config import get_settings
    from app.services.frame_sampler import extract_frame_at
    from app.services.oss_manager import OSSManager

    project = _get_owned_project(project_id, db, current_user)
    frame = extract_frame_at(request.clip_url, request.timestamp,
                             focus_y=request.focus_y)
    if not frame:
        raise HTTPException(status_code=422, detail="Could not extract a frame from that clip")

    oss = OSSManager(get_settings())
    key = oss.get_project_path(project_id, "posters", f"poster_{uuid.uuid4().hex[:8]}.jpg")
    poster_url = oss.upload_bytes(frame, key, content_type="image/jpeg")

    project.poster_url = poster_url
    db.commit()
    return {"poster_url": poster_url}


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_owned_project(project_id, db, current_user)
    db.delete(project)
    db.commit()
    return {"deleted": True, "project_id": project_id}


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    return project
