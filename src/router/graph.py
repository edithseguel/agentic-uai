"""Grafo LangGraph que enruta mensajes de un ecommerce."""

import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from src.router.prompts import (
    AGENTE_POSTVENTA_PROMPT,
    AGENTE_PREVENTA_PROMPT,
    RESPUESTA_GENERICA_PROMPT,
    ROUTER_PROMPT,
)

load_dotenv()


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
        "messages": [HumanMessage(content=state["mensaje"])],
    }


def agente_preventa(state: RouterState) -> RouterState:
    """Cascarón para futuras consultas de preventa."""
    return {"respuesta": AGENTE_PREVENTA_PROMPT.format(mensaje=state["mensaje"])}


def agente_postventa(state: RouterState) -> RouterState:
    """Cascarón para futuras consultas de postventa."""
    return {"respuesta": AGENTE_POSTVENTA_PROMPT.format(mensaje=state["mensaje"])}


def respuesta_generica(_: RouterState) -> RouterState:
    """Respuesta fija para mensajes fuera del contexto de la tienda."""
    return {"respuesta": RESPUESTA_GENERICA_PROMPT}


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

graph = builder.compile(checkpointer=MemorySaver())
