"""API HTTP para el router del chat de ecommerce."""

import logging
import os
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from src.router.graph import graph as router_graph

load_dotenv()
logger = logging.getLogger(__name__)
MODELO = os.getenv("MODELO", "gemini-3.5-flash-lite")

tags_metadata = [
    {"name": "salud", "description": "Estado del servicio y modelo configurado."},
    {"name": "chat", "description": "Enrutamiento de consultas de clientes."},
    {"name": "telegram", "description": "Webhook interno de Telegram."},
]

app = FastAPI(
    title="Ecommerce Router API",
    version="1.0.0",
    description=(
        "API que clasifica mensajes de un ecommerce y los enruta a **preventa**, "
        "**postventa** o **generica**. Preventa cubre consultas antes de comprar; "
        "postventa, pedidos o problemas posteriores; y generica, mensajes ajenos a la tienda."
    ),
    openapi_tags=tags_metadata,
)


class HealthResponse(BaseModel):
    """Estado público del servicio."""

    ok: bool = Field(description="Indica si la API está disponible.", examples=[True])
    modelo: str = Field(
        description="Nombre del modelo configurado mediante la variable MODELO.",
        examples=["gemini-3.5-flash-lite"],
    )


class ChatRequest(BaseModel):
    """Mensaje de un usuario que se debe enrutar."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "cliente-123",
                "texto": "¿tienen la polera azul en talla M?",
            }
        }
    )

    user_id: str = Field(
        min_length=1,
        description="Identificador estable del usuario; se usa como thread_id de LangGraph.",
        examples=["cliente-123"],
    )
    texto: str = Field(
        min_length=1,
        description="Mensaje que el router debe clasificar.",
        examples=["¿tienen la polera azul en talla M?"],
    )


class ChatResponse(BaseModel):
    """Resultado del enrutamiento y respuesta del agente destino."""

    ruta: Literal["preventa", "postventa", "generica"] = Field(
        description="Ruta seleccionada por el router.", examples=["preventa"]
    )
    motivo: str = Field(
        description="Motivo breve de la clasificación.",
        examples=["Consulta disponibilidad y talla antes de comprar."],
    )
    respuesta: str = Field(
        description="Respuesta generada por el agente de la ruta seleccionada.",
        examples=["Soy el agente de preventa. Recibí: ¿tienen la polera azul en talla M?. Pronto podré ayudarte con productos y compras."],
    )


class ErrorResponse(BaseModel):
    """Error público sin detalles internos."""

    detail: str = Field(
        description="Descripción segura del error para el cliente.",
        examples=["No fue posible procesar el mensaje con el modelo. Inténtalo nuevamente."],
    )


@app.get("/health", response_model=HealthResponse, tags=["salud"], summary="Comprobar la API")
def health() -> HealthResponse:
    """Devuelve el estado de la API y el modelo configurado."""
    return HealthResponse(ok=True, modelo=MODELO)


@app.post(
    "/chat",
    response_model=ChatResponse,
    tags=["chat"],
    summary="Enrutar un mensaje de ecommerce",
    responses={
        200: {"description": "Mensaje enrutado correctamente."},
        422: {"description": "El cuerpo no cumple el formato requerido."},
        502: {
            "model": ErrorResponse,
            "description": "El modelo no pudo procesar el mensaje.",
        },
    },
)
def chat(payload: ChatRequest) -> ChatResponse:
    """Ejecuta el grafo del router reutilizando memoria por usuario."""
    try:
        state = router_graph.invoke(
            {"mensaje": payload.texto},
            config={"configurable": {"thread_id": payload.user_id}},
        )
        return ChatResponse(
            ruta=state["ruta"], motivo=state["motivo"], respuesta=state["respuesta"]
        )
    except Exception:
        logger.exception("Error al enrutar el mensaje del usuario %s", payload.user_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible procesar el mensaje con el modelo. Inténtalo nuevamente.",
        ) from None


@app.post("/telegram", include_in_schema=False, tags=["telegram"])
def telegram(_: Any = Body(...)) -> dict[str, bool]:
    """Placeholder del webhook de Telegram."""
    return {"ok": True}
