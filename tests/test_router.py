import json
import os
from pathlib import Path
from typing import Literal, TypedDict

import pytest

from src.router.graph import graph

CASOS_PATH = Path(__file__).with_name("casos_router.json")


class CasoRouter(TypedDict):
    mensaje: str
    esperado: Literal["preventa", "postventa", "generica"]


def cargar_casos() -> list[CasoRouter]:
    with CASOS_PATH.open(encoding="utf-8") as archivo:
        return json.load(archivo)


CASOS = cargar_casos()


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="Define GOOGLE_API_KEY para ejecutar las pruebas de clasificación con Gemini.",
)
@pytest.mark.parametrize("casos", [CASOS], ids=["15-casos-router"])
def test_router_alcanza_minimo_de_aciertos(casos: list[CasoRouter]) -> None:
    """El modelo debe clasificar al menos 13 de los 15 casos de referencia."""
    aciertos = 0
    fallados: list[dict[str, str]] = []

    for indice, caso in enumerate(casos):
        state = graph.invoke(
            {"mensaje": caso["mensaje"]},
            config={"configurable": {"thread_id": f"pytest-router-{indice}"}},
        )
        if state["ruta"] == caso["esperado"]:
            aciertos += 1
        else:
            fallados.append(
                {
                    "mensaje": caso["mensaje"],
                    "esperado": caso["esperado"],
                    "obtenido": state["ruta"],
                }
            )

    assert aciertos >= 13, f"Aciertos: {aciertos}/15. Fallados: {fallados}"
