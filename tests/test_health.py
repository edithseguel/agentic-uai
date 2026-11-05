from fastapi.testclient import TestClient

from api.app import MODELO, app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "modelo": MODELO}
