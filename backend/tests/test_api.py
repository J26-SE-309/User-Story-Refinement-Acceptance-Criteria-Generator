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
