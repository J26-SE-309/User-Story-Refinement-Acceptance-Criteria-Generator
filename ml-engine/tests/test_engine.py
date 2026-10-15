import pytest
from story_ml.llm import LLMResponseError, LLMUnavailable
from story_ml.pipeline import refine_requirement
from story_ml.types import ContextDocument
from story_ml.config import LLMSettings
from story_ml.generation import parse_candidates



def criterion():
    return {
        "id": "AC1",
        "given": "a learner",
        "when": "the learner books a tutor",
        "then": "the learner books a tutor",
    }


def valid_payload():
    return {
        "candidates": [
            {
                "story_id": "REQ-1-S1",
                "user_story": "As a learner, I want to book a tutor, so that I can book a tutor.",
                "acceptance_criteria": [criterion()],
            },
            {
                "story_id": "REQ-1-S2",
                "user_story": "As a learner, I want to book a tutor, so that I can book a tutor.",
                "acceptance_criteria": [criterion()],
            },
        ]
    }


class FakeLLM:
    model = "fake-local"

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def generate_json(self, prompt):
        if self.error:
            raise self.error
        return self.payload


def docs():
    return [
        ContextDocument(
            "P1",
            "glossary-1",
            "glossary",
            "A learner books a tutor.",
            "glossary:booking",
        ),
        ContextDocument(
            "P2",
            "other-1",
            "business_rule",
            "An administrator approves refunds.",
            "rule:refund",
        ),
    ]


def test_pipeline_retrieves_only_selected_project_and_returns_winner():
    result = refine_requirement(
        "A learner can book a tutor.",
        "P1",
        docs(),
        llm=FakeLLM(valid_payload()),
        llm_settings=LLMSettings(candidate_count=2),
    )

    assert result.status == "completed"
    assert result.best_candidate is not None
    assert all(item.document.project_id == "P1" for item in result.retrieved_context)
    assert result.metadata["scores_are_heuristics"] is True


def test_malformed_json_is_rejected():
    with pytest.raises(LLMResponseError):
        parse_candidates({"unexpected": []}, 2)


def test_timeout_is_propagated_as_local_model_unavailable():
    with pytest.raises(LLMUnavailable):
        refine_requirement(
            "A learner can book a tutor.",
            "P1",
            [],
            llm=FakeLLM(error=LLMUnavailable("timed out")),
            llm_settings=LLMSettings(candidate_count=1),
        )


def test_empty_context_is_allowed_but_is_not_evidence():
    result = refine_requirement(
        "A learner can book a tutor.",
        "P1",
        [],
        llm=FakeLLM(valid_payload()),
        llm_settings=LLMSettings(candidate_count=2),
    )

    assert result.retrieved_context == []
    assert result.best_candidate is not None
    assert result.best_candidate.evaluation.scores["context_relevance"] < 1


def test_unsupported_claims_are_flagged_and_candidate_requires_review():
    payload = {
        "candidates": [
            {
                "story_id": "REQ-1-S1",
                "user_story": "As a learner, I want to book a tutor, so that I receive a guaranteed refund.",
                "acceptance_criteria": [criterion()],
            }
        ]
    }
    result = refine_requirement(
        "A learner can book a tutor.",
        "P1",
        docs(),
        llm=FakeLLM(payload),
        llm_settings=LLMSettings(candidate_count=1),
    )

    assert result.status == "review_required"
    assert result.best_candidate is None
        # assert result.risks
        # assert result.risks[0].kind == "unsupported_claim"
    assert result.risks
    assert result.risks[0].kind == "unsupported_claim"
    

def test_no_structurally_valid_candidate_returns_clear_error():
    with pytest.raises(LLMResponseError, match="No structurally valid"):
        refine_requirement(
            "A learner can book a tutor.",
            "P1",
            [],
            llm=FakeLLM(
                {"candidates": [{"user_story": "", "acceptance_criteria": []}]}
            ),
            llm_settings=LLMSettings(candidate_count=1),
        )


def test_explicit_context_conflict_is_distinguished_from_unsupported_claim():
    conflict = [
        ContextDocument(
            "P1",
            "rule-1",
            "business_rule",
            "A learner cannot book a tutor.",
            "rule:booking",
        ),
    ]
    conflict_payload = valid_payload()
    conflict_payload["candidates"][0]["acceptance_criteria"][0]["then"] = (
        "the learner can book a tutor"
    )
    conflict_payload["candidates"][1]["acceptance_criteria"][0]["then"] = (
        "the learner can book a tutor"
    )
    result = refine_requirement(
        "A learner can book a tutor.",
        "P1",
        conflict,
        llm=FakeLLM(conflict_payload),
        llm_settings=LLMSettings(candidate_count=2),
    )

    assert result.status == "review_required"
    assert any(finding.kind == "contradiction" for finding in result.risks)
