from fastapi.testclient import TestClient

from docsearch.main import app


def test_openapi_and_docs_available():
    client = TestClient(app)
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    payload = spec.json()
    assert payload["info"]["title"]
    paths = payload["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/ingest" in paths
    assert "/api/v1/query" in paths
    assert "/v1/chat/completions" in paths
    assert "/v1/models" in paths


def test_models_endpoint():
    client = TestClient(app)
    response = client.get("/v1/models")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["data"]}
    assert "docsearch-agentic" in ids
    assert "docsearch-direct" in ids


def test_health_endpoint_shape():
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded", "error"}
    names = {c["name"] for c in body["components"]}
    assert {"postgres", "ollama", "phoenix"} <= names
