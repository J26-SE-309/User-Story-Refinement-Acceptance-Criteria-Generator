"""Request and response models: the API contract of this service.

They mirror the JSON Schemas in Synapse-Web/contracts/story-refinement; change both together.
"""

from typing import Literal

from pydantic import BaseModel, Field


class RefinementRequest(BaseModel):
    requirement_id: str = Field(min_length=1, max_length=200)
    project_id: str | None = None
    validated_requirement: str = Field(min_length=1)
    context_reference: str | None = Field(default=None, description="Project-context package to retrieve from")
    project_context: str | None = Field(default=None, max_length=10_000)
    user_role: str | None = Field(default=None, min_length=1, max_length=200)


class ProjectCreate(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class ProjectContextCreate(BaseModel):
    context_key: str = Field(min_length=1, max_length=200)
    context_type: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1)
    source_reference: str | None = Field(default=None, max_length=500)
    authoritative: bool = True


class GenerationOptions(BaseModel):
    candidate_count: int = Field(default=3, ge=1, le=10)
    context_limit: int = Field(default=8, ge=1, le=50)


class StoryRefinementGenerateRequest(BaseModel):
    requirement_id: str = Field(min_length=1, max_length=200)
    project_id: str = Field(min_length=1, max_length=64)
    validated_requirement: str = Field(min_length=1)
    context: list[ProjectContextCreate] = Field(default_factory=list)
    options: GenerationOptions = Field(default_factory=GenerationOptions)


class ProjectResponse(ProjectCreate):
    model_config = {"from_attributes": True}


class ProjectContextResponse(ProjectContextCreate):
    id: int
    project_id: str
    model_config = {"from_attributes": True}


class ReviewDecisionRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=200)
    status: Literal["approved", "rejected", "edited", "changes_requested"]
    candidate_id: int | None = Field(default=None, gt=0)
    notes: str = ""


class ReviewDecisionResponse(ReviewDecisionRequest):
    id: int
    generation_id: int
    created_at: str


class RetrievedContextResponse(BaseModel):
    source_id: str
    source_type: str
    source_reference: str
    text: str
    score: float


class ProjectContextUpdate(BaseModel):
    context_type: str | None = Field(default=None, min_length=1, max_length=40)
    content: str | None = Field(default=None, min_length=1)
    source_reference: str | None = Field(default=None, max_length=500)
    authoritative: bool | None = None


class ExistingStoryCreate(BaseModel):
    story_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    source_reference: str | None = Field(default=None, max_length=500)
    acceptance_criteria: list[str] = Field(default_factory=list)


class ExistingStoryResponse(ExistingStoryCreate):
    id: int
    project_id: str
    model_config = {"from_attributes": True}


class ExistingStoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    source_reference: str | None = Field(default=None, max_length=500)
    acceptance_criteria: list[str] | None = None


class AcceptanceCriterion(BaseModel):
    id: str = Field(min_length=1)
    given: str = Field(min_length=1)
    when: str = Field(min_length=1)
    then: str = Field(min_length=1)


class QualityFinding(BaseModel):
    code: str
    message: str
    field: str | None = None


class QualityValidationRequest(BaseModel):
    user_story: str = Field(min_length=1)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    requirement_text: str | None = Field(default=None, min_length=1)
    assumptions: list[str] = Field(default_factory=list)


class QualityValidationResponse(BaseModel):
    valid: bool
    requires_human_review: bool = True
    errors: list[QualityFinding]
    warnings: list[QualityFinding]
    checks: dict[str, bool]


class StoryUpdateRequest(BaseModel):
    user_story: str = Field(min_length=1)
    acceptance_criteria: list[AcceptanceCriterion] = Field(min_length=1)


class StoryStatusResponse(BaseModel):
    story_id: str
    available: bool
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class CandidateResponse(BaseModel):
    id: int | None = None
    story_id: str
    user_story: str
    acceptance_criteria: list[AcceptanceCriterion]
    rank: int
    selected: bool
    quality_scores: dict[str, float]
    invest: dict[str, bool]
    explanations: dict[str, str]
    unsupported_assumptions: list[str]
    risks: list[dict[str, object]]
    ranking_rationale: str


class StoryRefinementGenerateResponse(BaseModel):
    generation_id: int
    requirement_id: str
    project_id: str
    status: Literal["completed", "review_required"]
    candidates: list[CandidateResponse]
    selected_candidate: CandidateResponse | None
    context_references: list[RetrievedContextResponse]
    risks: list[dict[str, object]]
    metadata: dict[str, object]


class InvestFlags(BaseModel):
    independent: bool
    negotiable: bool
    valuable: bool
    estimable: bool
    small: bool
    testable: bool


class QualityScores(BaseModel):
    invest: InvestFlags
    invest_score: float = Field(ge=0, le=1, description="Share of INVEST criteria met")
    completeness: float = Field(ge=0, le=1)
    clarity: float = Field(ge=0, le=1)
    testability: float = Field(ge=0, le=1)
    consistency: float = Field(ge=0, le=1)
    context_relevance: float = Field(ge=0, le=1)


class RefinedStory(BaseModel):
    refinement_id: int | None = Field(default=None, gt=0)
    requirement_id: str
    story_id: str
    story_title: str | None = None
    user_story: str
    user_role: str | None = None
    goal: str | None = None
    benefit: str | None = None
    acceptance_criteria: list[AcceptanceCriterion]
    quality_scores: QualityScores
    unsupported_assumptions: list[str] = []
    processing_time_ms: int = Field(ge=0)
    model_metadata: dict[str, str]
