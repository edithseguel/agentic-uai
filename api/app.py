"""API HTTP para el router del chat de ecommerce."""

import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
import httpx
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Security, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from src.router.graph import (
    cerrar_memoria,
    graph as router_graph,
    inicializar_memoria,
    tipo_memoria,
)
from src.router.mcp_shopify import inicializar_mcp_shopify

load_dotenv()
logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"
MODELO = os.getenv("MODELO", "gemini-3.5-flash-lite")
RESPUESTA_GIF = "¡Es el mejor gif del mundo!"
api_key_header = APIKeyHeader(name="X-API-Key", scheme_name="APIKeyHeader", auto_error=False)

tags_metadata = [
    {"name": "salud", "description": "Estado del servicio y modelo configurado."},
    {"name": "chat", "description": "Enrutamiento de consultas de clientes."},
    {"name": "telegram", "description": "Webhook interno de Telegram."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Abre una única conexión de memoria persistente durante la vida de la API."""
    await inicializar_mcp_shopify()
    inicializar_memoria()
    yield
    cerrar_memoria()


app = FastAPI(
    title="Ecommerce Router API",
    version="1.0.0",
    description=(
        "API que clasifica mensajes de un ecommerce y los enruta a **preventa**, "
        "**postventa** o **generica**. Preventa cubre consultas antes de comprar; "
        "postventa, pedidos o problemas posteriores; y generica, mensajes ajenos a la tienda."
    ),
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def interfaz_chat() -> FileResponse:
    """Sirve la interfaz web del chat."""
    return FileResponse(STATIC_DIR / "index.html")


class HealthResponse(BaseModel):
    """Estado público del servicio."""

    ok: bool = Field(description="Indica si la API está disponible.", examples=[True])
    modelo: str = Field(
        description="Nombre del modelo configurado mediante la variable MODELO.",
        examples=["gemini-3.5-flash-lite"],
    )
    memoria: Literal["ram", "postgres"] = Field(
        description="Almacenamiento de checkpoints activo.", examples=["postgres"]
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
    pasos: list["TraceStep"] = Field(
        description="Nodos y herramientas recorridos por el agente para responder."
    )


class TraceStep(BaseModel):
    """Paso del grafo ejecutado para responder al mensaje."""

    nodo: str = Field(description="Nodo o herramienta ejecutada.")
    detalle: str = Field(description="Descripción legible del paso.")


class ErrorResponse(BaseModel):
    """Error público sin detalles internos."""

    detail: str = Field(
        description="Descripción segura del error para el cliente.",
        examples=["No fue posible procesar el mensaje con el modelo. Inténtalo nuevamente."],
    )


class AuthCheckResponse(BaseModel):
    """Confirmación de una credencial válida para la interfaz web."""

    ok: bool = True


def verificar_api_key(api_key: str | None = Security(api_key_header)) -> None:
    """Autoriza el acceso a /chat mediante una clave configurada en el entorno."""
    clave_esperada = os.getenv("API_KEY")
    if not clave_esperada or api_key is None or not secrets.compare_digest(api_key, clave_esperada):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere una X-API-Key válida para usar el chat.",
        )


@app.get(
    "/auth/check",
    response_model=AuthCheckResponse,
    include_in_schema=False,
)
def comprobar_api_key(_: None = Depends(verificar_api_key)) -> AuthCheckResponse:
    """Valida la clave de la UI sin ejecutar el agente."""
    return AuthCheckResponse()


def es_gif(message: dict[str, Any]) -> bool:
    """Indica si el mensaje de Telegram contiene un GIF animado."""
    if isinstance(message.get("animation"), dict):
        return True

    document = message.get("document")
    return isinstance(document, dict) and document.get("mime_type") == "image/gif"


def ejecutar_chat_con_traza(payload: ChatRequest) -> ChatResponse:
    """Ejecuta el grafo y conserva los nodos y herramientas visitados."""
    estado: dict[str, Any] = {"mensaje": payload.texto}
    pasos: list[TraceStep] = []
    agentes_visitados: set[str] = set()
    nombres_agentes = {
        "agente_preventa": "Agente de preventa",
        "agente_postventa": "Agente de postventa",
    }

    def agregar_paso(nodo: str, detalle: str) -> None:
        pasos.append(TraceStep(nodo=nodo, detalle=detalle))

    eventos = router_graph.stream(
        {"mensaje": payload.texto},
        config={"configurable": {"thread_id": payload.user_id}},
        stream_mode="updates",
    )
    for evento in eventos:
        namespace: tuple[str, ...] = ()
        actualizacion = evento
        if (
            isinstance(evento, tuple)
            and len(evento) == 2
            and isinstance(evento[0], tuple)
        ):
            namespace, actualizacion = evento
        if not isinstance(actualizacion, dict):
            continue

        for nodo, cambio in actualizacion.items():
            if namespace:
                agente = namespace[0].split(":", maxsplit=1)[0]
                if nodo == "model" and agente in nombres_agentes:
                    agentes_visitados.add(agente)
                    agregar_paso(agente, nombres_agentes[agente])
                elif nodo == "tools" and isinstance(cambio, dict):
                    for mensaje in cambio.get("messages", []):
                        if getattr(mensaje, "type", "") == "tool":
                            nombre = getattr(mensaje, "name", "herramienta")
                            detalle = nombre.replace("_", " ").capitalize()
                            agregar_paso("herramienta", detalle)
                continue

            if nodo == "router":
                detalle = cambio.get("motivo", "Clasificando el mensaje.")
                agregar_paso(nodo, f"Clasificó el mensaje: {detalle}")
            elif nodo in nombres_agentes:
                if nodo not in agentes_visitados:
                    agregar_paso(nodo, nombres_agentes[nodo])
            elif nodo == "respuesta_generica":
                agregar_paso(nodo, "Generó una respuesta para la consulta.")
            elif nodo.startswith("finalizar_"):
                agregar_paso(nodo, "Preparó la respuesta final.")

            if isinstance(cambio, dict):
                estado.update(cambio)

    return ChatResponse(
        ruta=estado["ruta"],
        motivo=estado["motivo"],
        respuesta=estado["respuesta"],
        pasos=pasos,
    )


@app.get("/health", response_model=HealthResponse, tags=["salud"], summary="Comprobar la API")
def health() -> HealthResponse:
    """Devuelve el estado de la API y el modelo configurado."""
    return HealthResponse(ok=True, modelo=MODELO, memoria=tipo_memoria())


@app.post(
    "/chat",
    response_model=ChatResponse,
    tags=["chat"],
    summary="Enrutar un mensaje de ecommerce",
    responses={
        200: {"description": "Mensaje enrutado correctamente."},
        401: {
            "model": ErrorResponse,
            "description": "Falta la clave de API o no es válida.",
        },
        422: {"description": "El cuerpo no cumple el formato requerido."},
        502: {
            "model": ErrorResponse,
            "description": "El modelo no pudo procesar el mensaje.",
        },
    },
)
def chat(payload: ChatRequest, _: None = Depends(verificar_api_key)) -> ChatResponse:
    """Ejecuta el grafo del router reutilizando memoria por usuario."""
    try:
        return ejecutar_chat_con_traza(payload)
    except Exception:
        logger.exception("Error al enrutar el mensaje del usuario %s", payload.user_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible procesar el mensaje con el modelo. Inténtalo nuevamente.",
        ) from None


@app.post("/telegram", include_in_schema=False, tags=["telegram"])
async def telegram(
    update: dict[str, Any] = Body(...),
    telegram_secret: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> dict[str, bool]:
    """Procesa un mensaje Telegram y contesta sin exponer errores internos."""
    secret_esperado = os.getenv("TELEGRAM_SECRET")
    if not secret_esperado or telegram_secret != secret_esperado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook no autorizado.")

    message = update.get("message")
    if not isinstance(message, dict):
        return {"ok": True}

    chat = message.get("chat")
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    if chat_id is None:
        return {"ok": True}

    if es_gif(message):
        try:
            token = os.getenv("TELEGRAM_TOKEN")
            if not token:
                raise RuntimeError("TELEGRAM_TOKEN no está configurado")

            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": RESPUESTA_GIF},
                )
                if response.is_error:
                    logger.error("Telegram sendMessage respondió con estado %s", response.status_code)
            logger.info("Telegram: GIF recibido en chat %s", chat_id)
        except httpx.HTTPError as error:
            logger.error("Error HTTP enviando respuesta de GIF a Telegram: %s", type(error).__name__)
        except Exception:
            logger.exception("Error al procesar GIF de Telegram para chat %s", chat_id)
        return {"ok": True}

    if not isinstance(message.get("text"), str):
        return {"ok": True}

    texto = message["text"].strip()
    if not texto:
        return {"ok": True}

    try:
        state = await run_in_threadpool(
            router_graph.invoke,
            {"mensaje": texto},
            {"configurable": {"thread_id": str(chat_id)}},
        )
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            raise RuntimeError("TELEGRAM_TOKEN no está configurado")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": state["respuesta"]},
            )
            if response.is_error:
                logger.error("Telegram sendMessage respondió con estado %s", response.status_code)
                return {"ok": True}
        logger.info("Telegram: chat %s enrutado a %s", chat_id, state["ruta"])
    except httpx.HTTPError as error:
        logger.error("Error HTTP enviando respuesta a Telegram: %s", type(error).__name__)
    except Exception:
        logger.exception("Error al procesar el webhook de Telegram para chat %s", chat_id)

    return {"ok": True}
