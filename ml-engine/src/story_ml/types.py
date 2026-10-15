"""Typed data contracts for the context-aware refinement engine."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextDocument:
    project_id: str
    source_id: str
    source_type: str
    text: str
    source_reference: str


@dataclass(frozen=True)
class RetrievedContext:
    document: ContextDocument
    score: float



@dataclass(frozen=True)
class CandidateDraft:
    story_id: str
    user_story: str
    acceptance_criteria: list[AcceptanceCriterion]

@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    given: str
    when: str
    then: str

@dataclass(frozen=True)
class Finding:
    statement: str
    reason: str
    evidence: tuple[str, ...] = ()
    kind: str = "unsupported_claim"





@dataclass(frozen=True)
class RankedCandidate:
    candidate: CandidateDraft
    evaluation: QualityEvaluation
    rank: int
    ranking_rationale: str

@dataclass(frozen=True)
class QualityEvaluation:
    invest: dict[str, bool]
    scores: dict[str, float]
    explanations: dict[str, str]
    findings: list[Finding] = field(default_factory=list)
    valid: bool = True

    @property
    def overall_score(self) -> float:
        return self.scores.get("overall", 0.0)

        
@dataclass(frozen=True)
class RefinementResult:
    status: str
    candidates: list[RankedCandidate]
    best_candidate: RankedCandidate | None
    retrieved_context: list[RetrievedContext]
    risks: list[Finding]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible payload for the backend adapter."""

        def finding_payload(finding: Finding) -> dict[str, Any]:
            return {
                "statement": finding.statement,
                "reason": finding.reason,
                "evidence": list(finding.evidence),
                "kind": finding.kind,
            }

        def candidate_payload(item: RankedCandidate) -> dict[str, Any]:
            evaluation = item.evaluation
            return {
                "story_id": item.candidate.story_id,
                "user_story": item.candidate.user_story,
                "acceptance_criteria": [
                    {
                        "id": criterion.id,
                        "given": criterion.given,
                        "when": criterion.when,
                        "then": criterion.then,
                    }
                    for criterion in item.candidate.acceptance_criteria
                ],
                "rank": item.rank,
                "quality_scores": evaluation.scores,
                "invest": evaluation.invest,
                "explanations": evaluation.explanations,
                "findings": [
                    finding_payload(finding) for finding in evaluation.findings
                ],
                "ranking_rationale": item.ranking_rationale,
            }

        return {
            "status": self.status,
            "candidates": [candidate_payload(item) for item in self.candidates],
            "best_candidate": candidate_payload(self.best_candidate)
            if self.best_candidate
            else None,
            "retrieved_context": [
                {
                    "source_id": item.document.source_id,
                    "source_type": item.document.source_type,
                    "source_reference": item.document.source_reference,
                    "score": item.score,
                    "text": item.document.text,
                }
                for item in self.retrieved_context
            ],
            "risks": [finding_payload(finding) for finding in self.risks],
            "metadata": self.metadata,
        }
