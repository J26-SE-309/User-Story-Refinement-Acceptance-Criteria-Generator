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
