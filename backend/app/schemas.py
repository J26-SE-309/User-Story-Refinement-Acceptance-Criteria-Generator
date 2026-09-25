"""Request and response models: the API contract of this service.

They mirror the JSON Schemas in Synapse-Web/contracts/story-refinement; change both together.
"""

from pydantic import BaseModel, Field


class RefinementRequest(BaseModel):
    requirement_id: str
    project_id: str | None = None
    validated_requirement: str = Field(min_length=1)
    context_reference: str | None = Field(default=None, description="Project-context package to retrieve from")


class AcceptanceCriterion(BaseModel):
    id: str
    given: str
    when: str
    then: str


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
    requirement_id: str
    story_id: str
    user_story: str
    acceptance_criteria: list[AcceptanceCriterion]
    quality_scores: QualityScores
    unsupported_assumptions: list[str] = []
    processing_time_ms: int = Field(ge=0)
    model_metadata: dict[str, str]
