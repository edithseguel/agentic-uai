from fastapi.testclient import TestClient

from api.app import app


def test_chat_retorna_la_decision_del_router(monkeypatch) -> None:
    def invoke(_: dict, config: dict) -> dict:
        assert config["configurable"]["thread_id"] == "cliente-123"
        return {
            "ruta": "preventa",
            "motivo": "Consulta por una talla antes de comprar.",
            "respuesta": "Soy el agente de preventa.",
        }

    monkeypatch.setattr("api.app.router_graph.invoke", invoke)
    response = TestClient(app).post(
        "/chat",
        json={"user_id": "cliente-123", "texto": "¿Tienen talla M?"},
    )

    assert response.status_code == 200
    assert response.json()["ruta"] == "preventa"


def test_chat_sin_texto_devuelve_422() -> None:
    response = TestClient(app).post("/chat", json={"user_id": "cliente-123"})

    assert response.status_code == 422


def test_chat_devuelve_502_si_falla_el_modelo(monkeypatch) -> None:
    def invoke(_: dict, config: dict) -> dict:
        raise RuntimeError("detalle interno")

    monkeypatch.setattr("api.app.router_graph.invoke", invoke)
    response = TestClient(app).post(
        "/chat",
        json={"user_id": "cliente-123", "texto": "hola"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "No fue posible procesar el mensaje con el modelo. Inténtalo nuevamente."
    }


def test_telegram_esta_oculto_del_schema() -> None:
    client = TestClient(app)

    assert client.post("/telegram", json={"update_id": 1}).json() == {"ok": True}
    assert "/telegram" not in client.get("/openapi.json").json()["paths"]
