"""A dependency-free baseline generator used when the local model is not requested."""

import re
import time

from app.quality import validate_story_quality
from app.schemas import AcceptanceCriterion, QualityScores, RefinedStory, RefinementRequest


def _part_after(text: str, marker: str) -> str | None:
    match = re.search(rf"\b{re.escape(marker)}\s+(.+?)(?:[.!?]|$)", text, re.IGNORECASE)
    return match.group(1).strip(" .") if match else None


def _role_from_requirement(text: str) -> str | None:
    match = re.search(r"\bas a\s+(.+?)(?:,\s*i want\b|[.!?]|$)", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def generate_baseline(request: RefinementRequest) -> RefinedStory:
    started = time.perf_counter()
    requirement = request.validated_requirement.strip().rstrip(".")
    role = request.user_role.strip() if request.user_role else _role_from_requirement(requirement)
    role = role or "user"
    goal = _part_after(requirement, "I want") or requirement
    benefit = _part_after(requirement, "so that")
    assumptions: list[str] = []
    if not request.user_role and not _part_after(requirement, "as a"):
        assumptions.append("The requirement does not specify a user role; 'user' was used for review.")
    if not benefit:
        benefit = "the requested outcome is achieved"
        assumptions.append(
            "The requirement does not state the intended benefit; a neutral benefit was used for review."
        )

    story = f"As a {role}, I want {goal}, so that {benefit}."
    criteria = [
        AcceptanceCriterion(
            id="AC1",
            given="the validated requirement is in scope",
            when=f"the {role} performs the requested action",
            then=f"the system satisfies the requirement: {requirement}",
        )
    ]
    lowered = requirement.lower()
    if any(term in lowered for term in ("cannot", "must not", "unauthorised", "unauthorized", "invalid")):
        criteria.append(
            AcceptanceCriterion(
                id="AC2",
                given="the request does not meet the stated requirement conditions",
                when=f"the {role} attempts the requested action",
                then="the system does not complete the invalid request",
            )
        )
    if any(term in lowered for term in ("maximum", "minimum", "limit", "at least", "at most", "between")):
        criteria.append(
            AcceptanceCriterion(
                id=f"AC{len(criteria) + 1}",
                given="the stated boundary value is reached",
                when=f"the {role} performs the requested action at that boundary",
                then="the system applies the boundary stated in the requirement",
            )
        )

    quality = validate_story_quality(story, criteria, requirement, assumptions)
    complete = not any(item.code == "missing_criterion_field" for item in quality.errors)
    scores = QualityScores(
        invest={
            "independent": True,
            "negotiable": True,
            "valuable": bool(benefit),
            "estimable": True,
            "small": True,
            "testable": complete,
        },
        invest_score=1.0 if complete else 0.5,
        completeness=1.0 if benefit else 0.5,
        clarity=1.0 if role != "user" else 0.7,
        testability=1.0 if complete else 0.0,
        consistency=1.0,
        context_relevance=0.0 if not request.project_context else 0.5,
    )
    return RefinedStory(
        requirement_id=request.requirement_id,
        story_id=f"{request.requirement_id}-S1",
        story_title=goal[:120],
        user_story=story,
        user_role=role,
        goal=goal,
        benefit=benefit,
        acceptance_criteria=criteria,
        quality_scores=scores,
        unsupported_assumptions=assumptions,
        processing_time_ms=int((time.perf_counter() - started) * 1000),
        model_metadata={"model_version": "deterministic-baseline", "requires_human_review": "true"},
    )
