from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db_models import Project, ProjectAsset, StoredAsset
from .licensing import AuthenticatedPrincipal
from .object_service import get_asset


class ProjectNotFound(LookupError):
    pass


def get_project(session: Session, principal: AuthenticatedPrincipal, project_id: uuid.UUID) -> Project:
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == principal.user_id)
    )
    if project is None:
        raise ProjectNotFound(str(project_id))
    return project


def create_project(session: Session, principal: AuthenticatedPrincipal, name: str, description: str | None) -> Project:
    project = Project(user_id=principal.user_id, name=name.strip(), description=description)
    session.add(project)
    session.commit()
    return project


def list_projects(session: Session, principal: AuthenticatedPrincipal) -> list[Project]:
    return list(
        session.scalars(
            select(Project)
            .where(Project.user_id == principal.user_id)
            .order_by(Project.updated_at.desc())
        )
    )


def attach_asset(
    session: Session,
    principal: AuthenticatedPrincipal,
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> StoredAsset:
    get_project(session, principal, project_id)
    asset = get_asset(session, principal, asset_id)
    existing = session.get(ProjectAsset, (project_id, asset_id))
    if existing is None:
        session.add(ProjectAsset(project_id=project_id, asset_id=asset_id))
        session.commit()
    return asset


def project_assets(session: Session, principal: AuthenticatedPrincipal, project_id: uuid.UUID) -> list[StoredAsset]:
    get_project(session, principal, project_id)
    return list(
        session.scalars(
            select(StoredAsset)
            .join(ProjectAsset, ProjectAsset.asset_id == StoredAsset.id)
            .where(ProjectAsset.project_id == project_id)
            .order_by(ProjectAsset.created_at.desc())
        )
    )
