"""Version 1 of the refinement API.

Until the local LLM, context retrieval and candidate optimisation are plugged in, the
endpoint returns a placeholder story (model_version "stub") so the gateway and frontend
can be built against the real contract.
"""

import time

from fastapi import APIRouter

from app.schemas import AcceptanceCriterion, InvestFlags, QualityScores, RefinedStory, RefinementRequest

router = APIRouter(tags=["user story refinement"])


@router.post("/refine", response_model=RefinedStory)
def refine(request: RefinementRequest) -> RefinedStory:
    """Turn one validated requirement into a user story with acceptance criteria and quality scores."""
    started = time.perf_counter()
    no_flags = InvestFlags(
        independent=False, negotiable=False, valuable=False, estimable=False, small=False, testable=False
    )
    return RefinedStory(
        requirement_id=request.requirement_id,
        story_id=f"{request.requirement_id}-S1",
        user_story=f"Placeholder story for: {request.validated_requirement}",
        acceptance_criteria=[
            AcceptanceCriterion(id="AC1", given="(placeholder)", when="(placeholder)", then="(placeholder)")
        ],
        quality_scores=QualityScores(
            invest=no_flags,
            invest_score=0,
            completeness=0,
            clarity=0,
            testability=0,
            consistency=0,
            context_relevance=0,
        ),
        processing_time_ms=int((time.perf_counter() - started) * 1000),
        model_metadata={"model_version": "stub"},
    )
