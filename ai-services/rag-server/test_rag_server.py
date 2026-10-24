"""Automated tests for the Assessment Tracker RAG service.

Uses real retrieval/indexing logic with mocked assessment data and Ollama.
No Docker containers, database server or running LLM are required.
"""

import requests
import pytest

import app as rag_app
import corpus


SAMPLE_ASSIGNMENTS = [
    {
        "assignment_id": 1,
        "student_id": 1,
        "course_id": 41026,
        "title": "Software Architecture Report",
        "due_date": "2026-09-05",
        "weighting": 35.0,
        "status": "in_progress",
        "description": "Complete the software architecture report.",
    },
    {
        "assignment_id": 2,
        "student_id": 2,
        "course_id": 31271,
        "title": "Database Assignment",
        "due_date": "2026-10-15",
        "weighting": 25.0,
        "status": "not_started",
        "description": "Complete the database assignment.",
    },
]


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Create an isolated RAG service with mocked database records."""

    monkeypatch.setattr(corpus, "DOCUMENTS_DIR", tmp_path)
    monkeypatch.setattr(
        corpus,
        "_fetch_assignments",
        lambda student_id=None: SAMPLE_ASSIGNMENTS,
    )

    monkeypatch.setattr(rag_app, "_index", None)
    monkeypatch.setattr(rag_app, "_report", {})

    rag_app.app.config["TESTING"] = True

    yield rag_app.app.test_client()

    rag_app._index = None
    rag_app._report = {}


def test_health_indexes_assessments(client):
    response = client.get("/health")

    assert response.status_code == 200

    body = response.get_json()

    assert body["status"] == "ok"
    assert body["index"]["sources"]["assignments"] == 2
    assert body["index"]["unavailable"] == []
    assert body["passages"] >= 2


def test_grounded_answer_has_citations(client, monkeypatch):
    monkeypatch.setattr(
        rag_app,
        "_ask_model",
        lambda question, results: (
            "The Software Architecture Report is due on 2026-09-05.",
            None,
        ),
    )

    response = client.post(
        "/query",
        json={
            "question": "When is the Software Architecture Report due?",
            "top_k": 4,
            "feature": "assessments",
        },
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["grounded"] is True
    assert body["generated"] is True
    assert "2026-09-05" in body["answer"]
    assert body["citations"]
    assert body["confidence"] in ("high", "medium", "low")
    assert any(
        "assessment tracker, assignment 1" == citation["source"]
        for citation in body["citations"]
    )


def test_assessment_index_filters_by_student(monkeypatch, tmp_path):
    monkeypatch.setattr(corpus, "DOCUMENTS_DIR", tmp_path)
    monkeypatch.setattr(
        corpus,
        "_fetch_assignments",
        lambda student_id=None: SAMPLE_ASSIGNMENTS,
    )

    index, report = corpus.build_index(student_id=1)

    assert report["sources"]["assignments"] == 1
    assert report["passages"] == 1

    results = index.search("Software Architecture Report", top_k=5)

    assert results
    assert all(
        "assignment 1" in result["source"]
        for result in results
    )


def test_missing_question_is_rejected(client):
    response = client.post("/query", json={})

    assert response.status_code == 400
    assert "'question' is required" in response.get_json()["error"]


def test_no_relevant_context_returns_insufficient(client, monkeypatch):
    class EmptyIndex:
        def search(self, question, top_k=4):
            return []

    monkeypatch.setattr(rag_app, "_index", EmptyIndex())

    def should_not_call_model(question, results):
        raise AssertionError("Model called without retrieved evidence")

    monkeypatch.setattr(
        rag_app,
        "_ask_model",
        should_not_call_model,
    )

    response = client.post(
        "/query",
        json={"question": "An unrelated question"},
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["grounded"] is False
    assert body["insufficient_context"] is True
    assert body["confidence"] == "insufficient"
    assert body["citations"] == []


def test_model_refusal_is_honoured(client, monkeypatch):
    monkeypatch.setattr(
        rag_app,
        "_ask_model",
        lambda question, results: ("INSUFFICIENT_CONTEXT", None),
    )

    response = client.post(
        "/query",
        json={"question": "When is the Software Architecture Report due?"},
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["grounded"] is False
    assert body["insufficient_context"] is True
    assert body["confidence"] == "insufficient"
    assert "INSUFFICIENT_CONTEXT" not in body["answer"]


def test_ollama_unavailable_uses_extractive_fallback(client, monkeypatch):
    monkeypatch.setattr(
        rag_app,
        "_ask_model",
        lambda question, results: (None, "model unavailable"),
    )

    response = client.post(
        "/query",
        json={"question": "When is the Software Architecture Report due?"},
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["grounded"] is True
    assert body["generated"] is False
    assert body["citations"]
    assert "2026-09-05" in body["answer"]
    assert "model unavailable" in body["note"]


def test_reindex_updates_assessment_records(client):
    response = client.post("/reindex", json={"student_id": 1})

    assert response.status_code == 200

    body = response.get_json()

    assert body["reindexed"] is True
    assert body["index"]["sources"]["assignments"] == 1


def test_assessment_database_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(corpus, "DOCUMENTS_DIR", tmp_path)

    # Documentation should still be indexed if the database is down.
    (tmp_path / "overview.md").write_text(
        "The Assessment Tracker manages student assignments.",
        encoding="utf-8",
    )

    def unavailable(student_id=None):
        raise requests.ConnectionError("Assessment database unavailable")

    monkeypatch.setattr(
        corpus,
        "_fetch_assignments",
        unavailable,
    )

    index, report = corpus.build_index(student_id=1)

    assert report["sources"]["assignments"] == 0
    assert report["sources"]["documents"] == 1
    assert len(index) == 1
    assert any(
        item["source"] == "assignments"
        for item in report["unavailable"]
    )
