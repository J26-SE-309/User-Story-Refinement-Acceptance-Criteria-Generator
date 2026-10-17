def test_refine_returns_the_contract_shape(client):
    response = client.post(
        "/api/v1/refine", json={"requirement_id": "REQ-1", "validated_requirement": "Students can book a tutor."}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requirement_id"] == "REQ-1"
    assert body["acceptance_criteria"], "at least one acceptance criterion"
    assert {"invest", "completeness", "testability"} <= set(body["quality_scores"])


def test_refine_rejects_an_empty_requirement(client):
    response = client.post("/api/v1/refine", json={"requirement_id": "REQ-1", "validated_requirement": ""})
    assert response.status_code == 422


def test_refine_persists_requirement_candidate_criteria_and_evaluation(client, test_session_factory):
    response = client.post(
        "/api/v1/refine",
        json={
            "requirement_id": "REQ-2",
            "project_id": "PROJ-1",
            "validated_requirement": "A learner can book a tutor.",
            "context_reference": "context-42",
        },
    )

    assert response.status_code == 200
    assert response.json()["refinement_id"] > 0

    from app.models import CandidateQualityEvaluation, RefinementRun, StoryCandidate, ValidatedRequirement

    with test_session_factory() as session:
        run = session.get(RefinementRun, response.json()["refinement_id"])
        assert run is not None
        assert session.get(ValidatedRequirement, "REQ-2") is not None
        candidate = session.query(StoryCandidate).filter_by(run_id=run.id).one()
        assert candidate.acceptance_criteria
        assert session.query(CandidateQualityEvaluation).filter_by(candidate_id=candidate.id).one()


def test_review_updates_run_status_and_persists_decision(client, test_session_factory):
    generation = client.post(
        "/api/v1/refine", json={"requirement_id": "REQ-3", "validated_requirement": "A user can sign in."}
    ).json()

    response = client.post(
        f"/api/v1/refinements/{generation['refinement_id']}/review",
        json={"reviewer": "reviewer@example.test", "status": "approved", "notes": "Ready."},
    )

    assert response.status_code == 200
    from app.models import RefinementRun, ReviewDecision

    with test_session_factory() as session:
        run = session.get(RefinementRun, generation["refinement_id"])
        assert run.status == "approved"
        assert session.query(ReviewDecision).filter_by(run_id=run.id).one().reviewer == "reviewer@example.test"


def test_project_context_endpoint_persists_glossary_entry_and_rejects_duplicate_key(client):
    project = client.post("/api/v1/projects", json={"id": "PROJ-CTX", "name": "Tutor platform"})
    assert project.status_code == 201

    context = client.post(
        "/api/v1/projects/PROJ-CTX/context",
        json={
            "context_key": "booking.term",
            "context_type": "glossary",
            "content": "A booking reserves one available tutoring slot.",
            "source_reference": "policy-1",
        },
    )
    assert context.status_code == 201
    assert context.json()["project_id"] == "PROJ-CTX"

    duplicate = client.post(
        "/api/v1/projects/PROJ-CTX/context",
        json={"context_key": "booking.term", "context_type": "business_rule", "content": "Duplicate."},
    )
    assert duplicate.status_code == 409


def test_story_refinement_generate_persists_candidates_and_can_be_retrieved(client, monkeypatch):
    from story_ml.types import (
        AcceptanceCriterion,
        CandidateDraft,
        QualityEvaluation,
        RankedCandidate,
        RefinementResult,
    )

    client.post("/api/v1/projects", json={"id": "PROJ-GEN", "name": "Generation project"})
    candidate = CandidateDraft(
        story_id="REQ-GEN-S1",
        user_story="As a learner, I want to book a tutor, so that I can learn.",
        acceptance_criteria=[
            AcceptanceCriterion(
                id="AC1",
                given="a learner",
                when="the learner books a tutor",
                then="the booking is created",
            )
        ],
    )
    evaluation = QualityEvaluation(
        invest={
            "independent": True,
            "negotiable": True,
            "valuable": True,
            "estimable": True,
            "small": True,
            "testable": True,
        },
        scores={
            "invest": 1.0,
            "clarity": 1.0,
            "completeness": 1.0,
            "testability": 1.0,
            "consistency": 1.0,
            "context_relevance": 0.5,
            "acceptance_criteria_coverage": 1.0,
            "overall": 0.93,
        },
        explanations={"overall": "deterministic test result"},
    )
    ranked = RankedCandidate(candidate, evaluation, 1, "highest configured score")
    fake_result = RefinementResult(
        status="completed",
        candidates=[ranked],
        best_candidate=ranked,
        retrieved_context=[],
        risks=[],
        metadata={"model": "test-local"},
    )

    import story_ml.pipeline

    monkeypatch.setattr(story_ml.pipeline, "refine_requirement", lambda *args, **kwargs: fake_result)
    response = client.post(
        "/api/v1/story-refinement/generate",
        json={
            "project_id": "PROJ-GEN",
            "requirement_id": "REQ-GEN",
            "validated_requirement": "A learner can book a tutor.",
            "options": {"candidate_count": 1},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["selected_candidate"]["story_id"] == "REQ-GEN-S1"
    retrieved = client.get(f"/api/v1/story-refinement/{body['generation_id']}")
    assert retrieved.status_code == 200
    assert retrieved.json()["candidates"][0]["quality_scores"]["overall"] == 0.93


def test_story_refinement_generate_returns_not_found_for_missing_project(client):
    response = client.post(
        "/api/v1/story-refinement/generate",
        json={
            "project_id": "MISSING",
            "requirement_id": "REQ-MISSING",
            "validated_requirement": "A learner can book a tutor.",
        },
    )
    assert response.status_code == 404


def test_story_refinement_generate_maps_local_model_failure(client, monkeypatch):
    from story_ml.llm import LLMUnavailable

    client.post("/api/v1/projects", json={"id": "PROJ-FAIL", "name": "Failure project"})
    import story_ml.pipeline

    monkeypatch.setattr(
        story_ml.pipeline,
        "refine_requirement",
        lambda *args, **kwargs: (_ for _ in ()).throw(LLMUnavailable("test timeout")),
    )
    response = client.post(
        "/api/v1/story-refinement/generate",
        json={
            "project_id": "PROJ-FAIL",
            "requirement_id": "REQ-FAIL",
            "validated_requirement": "A learner can book a tutor.",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Local model unavailable."
