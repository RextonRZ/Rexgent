import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import get_current_user
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


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
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


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
