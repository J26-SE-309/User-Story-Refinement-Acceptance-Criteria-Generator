from app.models import ValidatedRequirement


def test_requirements_list_only_returns_validated_records(client, test_session_factory):
    with test_session_factory() as session:
        session.add_all(
            [
                ValidatedRequirement(
                    id="REQ-APPROVED",
                    project_id="PROJECT-A",
                    domain="education",
                    text="A learner can search tutors.",
                    context_text="Tutor profiles are searchable.",
                    validation_status="validated",
                ),
                ValidatedRequirement(
                    id="REQ-PENDING",
                    project_id="PROJECT-A",
                    text="A learner can export results.",
                    validation_status="pending_review",
                ),
            ]
        )
        session.commit()

    response = client.get("/api/v1/requirements", params={"project_id": "PROJECT-A"})

    assert response.status_code == 200
    assert [item["requirement_id"] for item in response.json()] == ["REQ-APPROVED"]
    assert response.json()[0]["domain"] == "education"


def test_requirement_detail_rejects_pending_and_missing_records(client, test_session_factory):
    with test_session_factory() as session:
        session.add(
            ValidatedRequirement(
                id="REQ-PENDING-DETAIL",
                text="A pending requirement.",
                validation_status="pending_review",
            )
        )
        session.commit()

    assert client.get("/api/v1/requirements/REQ-PENDING-DETAIL").status_code == 404
    assert client.get("/api/v1/requirements/REQ-MISSING").status_code == 404


def test_refine_requires_validated_requirement(client):
    response = client.post("/api/v1/refine", json={"requirement_id": "REQ-NOT-APPROVED"})

    assert response.status_code == 404


def test_refinement_history_is_preserved_for_one_requirement(client, test_session_factory):
    first = client.post("/api/v1/refine", json={"requirement_id": "REQ-1"})
    second = client.post("/api/v1/refine", json={"requirement_id": "REQ-1"})

    assert first.status_code == 200
    assert second.status_code == 200
    from app.models import RefinementRun

    with test_session_factory() as session:
        runs = session.query(RefinementRun).filter_by(requirement_id="REQ-1").all()
        assert len(runs) == 2
