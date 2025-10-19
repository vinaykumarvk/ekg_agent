import os
import types
import pytest

from fastapi.testclient import TestClient


def make_mock_openai_client():
    """Minimal mock of OpenAI client used by our code paths."""
    # responses.create(model=..., input=[...]) -> object with .output_text
    def responses_create(model: str, input: list, max_output_tokens: int = None, temperature: float = None):
        class Resp:
            output_text = "This is a mocked answer. [1]"
        return Resp()

    # vector_stores.search(...) -> with .data entries having .content[0].text
    def vector_search(vector_store_id: str, query: str):
        class Hit:
            def __init__(self, text: str, filename: str = "doc.txt", score: float = 0.5):
                self.filename = filename
                self.file_id = "file_1"
                self.score = score
                self.content = [types.SimpleNamespace(text=text)]

        class Res:
            data = [Hit(text=f"Chunk for: {query}")]

        return Res()

    # embeddings.create(model=..., input=...) -> vector
    def embeddings_create(model: str, input: str):
        class Emb:
            def __init__(self):
                self.data = [types.SimpleNamespace(embedding=[0.1, 0.2, 0.3])]
        return Emb()

    client = types.SimpleNamespace()
    client.responses = types.SimpleNamespace(create=responses_create)
    client.vector_stores = types.SimpleNamespace(search=vector_search)
    client.embeddings = types.SimpleNamespace(create=embeddings_create)
    return client


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")


def test_health_imports_and_env():
    from api.main import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"healthy", "degraded"}
    assert "available_modes" in body


def test_answer_vector_mode(monkeypatch):
    # Force intent to vector to avoid KG requirements
    from agents.tools import intent_clarification

    def fake_intent(_q: str):
        return intent_clarification.Intent(route="vector", hops=1, top_k=6)

    monkeypatch.setattr(intent_clarification, "clarify_intent", fake_intent)

    # Inject mock OpenAI client into dependency provider
    import api.main as main_mod

    def fake_get_client():
        return make_mock_openai_client()

    # Clear cache on provider and set fake
    main_mod.get_client.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.setattr(main_mod, "get_client", fake_get_client)

    app = main_mod.app
    client = TestClient(app)

    payload = {
        "question": "Give an overview of the process.",
        "vectorstore_id": "vs_dummy",
        "params": {"_mode": "concise"}
    }

    r = client.post("/v1/answer", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("markdown", ""), str)
    # Should include normalized fields even if sources/meta are None
    assert "sources" in data
    assert "meta" in data



