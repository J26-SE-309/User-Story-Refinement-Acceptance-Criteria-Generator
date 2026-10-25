"""End-to-end context-aware local refinement pipeline."""

from story_ml.config import LLMSettings, RankingSettings
from story_ml.evaluation import rank_candidates
from story_ml.generation import generate_candidates
from story_ml.llm import OllamaClient
from story_ml.retrieval import SemanticContextRetriever
from story_ml.types import ContextDocument, RankedCandidate, RefinementResult


def refine_requirement(
    requirement: str,
    project_id: str,
    documents: list[ContextDocument],
    llm: OllamaClient | None = None,
    llm_settings: LLMSettings | None = None,
    ranking_settings: RankingSettings | None = None,
) -> RefinementResult:
    if not requirement.strip():
        raise ValueError("Requirement must not be empty.")
    llm_settings = llm_settings or LLMSettings()
    retrieved = SemanticContextRetriever(documents).retrieve(project_id, requirement)
    client = llm or OllamaClient(
        llm_settings.base_url, llm_settings.model, llm_settings.timeout_seconds
    )
    candidates = generate_candidates(
        client, requirement, retrieved, llm_settings.candidate_count
    )
    ranked, risks = rank_candidates(
        candidates, requirement, retrieved, ranking_settings
    )
    ranked_candidates = [
        RankedCandidate(
            candidate=candidate,
            evaluation=evaluation,
            rank=index,
            ranking_rationale=f"Ranked by configured quality weights; overall heuristic score {evaluation.overall_score:.3f}.",
        )
        for index, (candidate, evaluation) in enumerate(ranked, start=1)
    ]
    return RefinementResult(
        status="completed" if ranked_candidates else "review_required",
        candidates=ranked_candidates,
        best_candidate=ranked_candidates[0] if ranked_candidates else None,
        retrieved_context=retrieved,
        risks=risks,
        metadata={
            "model": client.model,
            "candidate_count_requested": llm_settings.candidate_count,
            "retrieval_method": "tfidf_cosine",
            "scores_are_heuristics": True,
        },
    )
