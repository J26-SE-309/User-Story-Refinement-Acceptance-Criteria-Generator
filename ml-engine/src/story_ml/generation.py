"""Prompt construction and strict candidate parsing."""

import json
from collections.abc import Mapping

from story_ml.llm import LLMResponseError, OllamaClient
from story_ml.types import AcceptanceCriterion, CandidateDraft, RetrievedContext


def build_prompt(
    requirement: str, context: list[RetrievedContext], candidate_count: int
) -> str:
    evidence = [
        {
            "source_reference": item.document.source_reference,
            "source_type": item.document.source_type,
            "text": item.document.text,
        }
        for item in context
    ]
    return (
        "Generate exactly the requested number of alternative Agile user-story candidates. "
        "Use only the requirement and supplied evidence; do not invent rules or facts. "
        "Return JSON only with key candidates. Each candidate must have story_id, user_story, "
        "and acceptance_criteria. Every criterion must have id, given, when, then. "
        'The user_story must follow "As a [user], I want [goal], so that [benefit]." '
        f"Candidate count: {candidate_count}\n"
        f"Requirement: {requirement}\nEvidence: {json.dumps(evidence)}"
    )


def parse_candidates(
    payload: Mapping[str, object], expected_count: int
) -> list[CandidateDraft]:
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise LLMResponseError("Candidate JSON must contain a candidates array.")
    candidates: list[CandidateDraft] = []
    for index, raw in enumerate(raw_candidates, start=1):
        if not isinstance(raw, dict):
            continue
        story_id = raw.get("story_id", f"C{index}")
        user_story = raw.get("user_story")
        raw_criteria = raw.get("acceptance_criteria")
        if (
            not isinstance(story_id, str)
            or not isinstance(user_story, str)
            or not isinstance(raw_criteria, list)
        ):
            continue
        criteria: list[AcceptanceCriterion] = []
        for criterion in raw_criteria:
            if not isinstance(criterion, dict) or not all(
                isinstance(criterion.get(key), str)
                for key in ("id", "given", "when", "then")
            ):
                continue
            criteria.append(
                AcceptanceCriterion(
                    **{key: criterion[key] for key in ("id", "given", "when", "then")}
                )
            )
        if criteria and user_story.strip():
            candidates.append(
                CandidateDraft(
                    story_id=story_id,
                    user_story=user_story.strip(),
                    acceptance_criteria=criteria,
                )
            )
    if not candidates:
        raise LLMResponseError("No structurally valid candidates were returned.")
    return candidates[:expected_count]


def generate_candidates(
    client: OllamaClient,
    requirement: str,
    context: list[RetrievedContext],
    candidate_count: int,
) -> list[CandidateDraft]:
    payload = client.generate_json(build_prompt(requirement, context, candidate_count))
    return parse_candidates(payload, candidate_count)
