"""Grafo LangGraph que enruta mensajes de un ecommerce."""

import logging
import os
from pathlib import Path
from typing import Annotated, Any, Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from src.router.prompts import (
    AGENTE_POSTVENTA_PROMPT,
    AGENTE_PREVENTA_PROMPT,
    RESPUESTA_GENERICA_FALLBACK,
    RESPUESTA_GENERICA_PROMPT,
    ROUTER_PROMPT,
)

load_dotenv()
logger = logging.getLogger(__name__)
TIENDA_PATH = Path(__file__).resolve().parents[2] / "data" / "tienda.md"


class Decision(BaseModel):
    """Decisión estructurada producida por el modelo en el nodo router."""

    ruta: Literal["preventa", "postventa", "generica"] = Field(
        description="A qué agente va el mensaje."
    )
    motivo: str = Field(description="Una frase: por qué esa ruta.")


class RouterState(TypedDict, total=False):
    """Estado compartido y persistido por hilo de conversación."""

    mensaje: str
    ruta: Literal["preventa", "postventa", "generica"]
    motivo: str
    respuesta: str
    messages: Annotated[list, add_messages]


def crear_llm() -> ChatGoogleGenerativeAI:
    """Crea el modelo configurado mediante variables de entorno."""
    modelo = os.getenv("MODELO", "gemini-3.5-flash-lite")
    return ChatGoogleGenerativeAI(model=modelo)


def router(state: RouterState) -> RouterState:
    """Clasifica el mensaje y guarda la decisión estructurada."""
    llm = crear_llm().with_structured_output(Decision)
    decision = llm.invoke([
        ("system", ROUTER_PROMPT),
        ("human", state["mensaje"]),
    ])
    return {
        "ruta": decision.ruta,
        "motivo": decision.motivo,
    }


def agente_preventa(state: RouterState) -> RouterState:
    """Cascarón para futuras consultas de preventa."""
    respuesta = AGENTE_PREVENTA_PROMPT.format(mensaje=state["mensaje"])
    return {
        "respuesta": respuesta,
        "messages": [
            HumanMessage(content=state["mensaje"]),
            AIMessage(content=respuesta),
        ],
    }


def agente_postventa(state: RouterState) -> RouterState:
    """Cascarón para futuras consultas de postventa."""
    respuesta = AGENTE_POSTVENTA_PROMPT.format(mensaje=state["mensaje"])
    return {
        "respuesta": respuesta,
        "messages": [
            HumanMessage(content=state["mensaje"]),
            AIMessage(content=respuesta),
        ],
    }


def respuesta_generica(state: RouterState) -> RouterState:
    """Responde consultas generales con el contexto autorizado de la tienda."""
    mensaje_usuario = HumanMessage(content=state["mensaje"])
    try:
        tienda = TIENDA_PATH.read_text(encoding="utf-8")
        respuesta_modelo = crear_llm().invoke(
            [
                SystemMessage(content=RESPUESTA_GENERICA_PROMPT.format(tienda=tienda)),
                *state.get("messages", []),
                mensaje_usuario,
            ]
        )
        respuesta = str(respuesta_modelo.content).strip()
        if not respuesta:
            raise ValueError("El modelo devolvió una respuesta vacía")
    except Exception:
        logger.exception("No fue posible generar la respuesta genérica; se usa respaldo.")
        respuesta = RESPUESTA_GENERICA_FALLBACK

    return {
        "respuesta": respuesta,
        "messages": [mensaje_usuario, AIMessage(content=respuesta)],
    }


def seleccionar_ruta(
    state: RouterState,
) -> Literal["agente_preventa", "agente_postventa", "respuesta_generica"]:
    """Dirige la ejecución al cascarón definido por la clasificación."""
    rutas = {
        "preventa": "agente_preventa",
        "postventa": "agente_postventa",
        "generica": "respuesta_generica",
    }
    return rutas[state["ruta"]]  # type: ignore[return-value]


def crear_grafo(checkpointer: Any) -> Any:
    """Compila el router con el almacenamiento de checkpoints indicado."""
    builder = StateGraph(RouterState)
    builder.add_node("router", router)
    builder.add_node("agente_preventa", agente_preventa)
    builder.add_node("agente_postventa", agente_postventa)
    builder.add_node("respuesta_generica", respuesta_generica)
    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", seleccionar_ruta)
    builder.add_edge("agente_preventa", END)
    builder.add_edge("agente_postventa", END)
    builder.add_edge("respuesta_generica", END)
    return builder.compile(checkpointer=checkpointer)


class GrafoRouter:
    """Fachada estable del grafo para poder cambiar su checkpointer al iniciar."""

    def __init__(self) -> None:
        self._graph = crear_grafo(MemorySaver())

    def configurar(self, checkpointer: Any) -> None:
        self._graph = crear_grafo(checkpointer)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return self._graph.invoke(*args, **kwargs)

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        return self._graph.stream(*args, **kwargs)

    def get_graph(self, *args: Any, **kwargs: Any) -> Any:
        return self._graph.get_graph(*args, **kwargs)

    def inicializar_memoria(self) -> Literal["ram", "postgres"]:
        return inicializar_memoria()

    def cerrar_memoria(self) -> None:
        cerrar_memoria()


graph = GrafoRouter()
_pool: Any | None = None
_tipo_memoria: Literal["ram", "postgres"] = "ram"


def inicializar_memoria() -> Literal["ram", "postgres"]:
    """Configura Postgres si está disponible; de lo contrario conserva memoria RAM."""
    global _pool, _tipo_memoria
    if _pool is not None:
        return _tipo_memoria

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.info("Memoria del router en RAM: DATABASE_URL no está configurada.")
        return "ram"

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool

        pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=2,
            timeout=5,
            check=ConnectionPool.check_connection,
            kwargs={"autocommit": True, "prepare_threshold": 0},
            open=False,
        )
        pool.open(wait=True)
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()
        graph.configurar(checkpointer)
        _pool = pool
        _tipo_memoria = "postgres"
        logger.info("Memoria del router conectada a PostgreSQL.")
    except Exception as error:
        logger.warning(
            "Memoria del router en RAM: no fue posible conectar a PostgreSQL (%s).",
            type(error).__name__,
        )
        try:
            pool.close()  # type: ignore[name-defined]
        except Exception:
            pass
    return _tipo_memoria


def cerrar_memoria() -> None:
    """Cierra el pool de PostgreSQL abierto por esta ejecución."""
    global _pool, _tipo_memoria
    if _pool is not None:
        _pool.close()
        _pool = None
        _tipo_memoria = "ram"
        graph.configurar(MemorySaver())


def tipo_memoria() -> Literal["ram", "postgres"]:
    """Devuelve el almacenamiento de checkpoints activo."""
    return _tipo_memoria
