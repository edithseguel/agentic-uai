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


def test_telegram_ignora_updates_sin_texto_y_esta_oculto(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_SECRET", "secreto-de-prueba")
    client = TestClient(app)

    response = client.post(
        "/telegram",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "secreto-de-prueba"},
    )

    assert response.json() == {"ok": True}
    assert "/telegram" not in client.get("/openapi.json").json()["paths"]


def test_telegram_rechaza_un_secreto_invalido(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_SECRET", "secreto-de-prueba")

    response = TestClient(app).post("/telegram", json={"message": {}})

    assert response.status_code == 403


def test_telegram_enruta_y_envia_respuesta(monkeypatch) -> None:
    enviados: list[tuple[str, dict]] = []

    def invoke(_: dict, config: dict) -> dict:
        assert config["configurable"]["thread_id"] == "9988"
        return {
            "ruta": "preventa",
            "motivo": "Consulta antes de comprar.",
            "respuesta": "Soy el agente de preventa.",
        }

    class FakeResponse:
        is_error = False

    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, json: dict) -> FakeResponse:
            enviados.append((url, json))
            return FakeResponse()

    monkeypatch.setenv("TELEGRAM_SECRET", "secreto-de-prueba")
    monkeypatch.setenv("TELEGRAM_TOKEN", "token-de-prueba")
    monkeypatch.setattr("api.app.router_graph.invoke", invoke)
    monkeypatch.setattr("api.app.httpx.AsyncClient", FakeAsyncClient)

    response = TestClient(app).post(
        "/telegram",
        json={"message": {"chat": {"id": 9988}, "text": "¿Tienen talla M?"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "secreto-de-prueba"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert enviados == [
        (
            "https://api.telegram.org/bottoken-de-prueba/sendMessage",
            {"chat_id": 9988, "text": "Soy el agente de preventa."},
        )
    ]
