from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import ValidatedRequirement

router = APIRouter(
    prefix="/requirements",
    tags=["validated requirements"],
)


def _requirement_response(item: ValidatedRequirement) -> dict[str, str | None]:
    return {
        "requirement_id": item.id,
        "project_id": item.project_id,
        "domain": item.domain,
        "validated_requirement": item.text,
        "context_text": item.context_text,
    }


@router.get("")
def list_requirements(
    session: Annotated[Session, Depends(get_session)],
    project_id: str | None = None,
) -> list[dict[str, str | None]]:
    query = select(ValidatedRequirement).where(
        ValidatedRequirement.validation_status == "validated"
    )

    if project_id:
        query = query.where(ValidatedRequirement.project_id == project_id)

    requirements = session.scalars(
        query.order_by(ValidatedRequirement.created_at.desc())
    ).all()
    return [_requirement_response(item) for item in requirements]


@router.get("/{requirement_id}")
def get_requirement(
    requirement_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str | None]:
    item = session.scalar(
        select(ValidatedRequirement).where(
            ValidatedRequirement.id == requirement_id,
            ValidatedRequirement.validation_status == "validated",
        )
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Validated requirement not found",
        )

    return _requirement_response(item)
