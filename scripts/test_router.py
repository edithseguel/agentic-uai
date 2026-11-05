"""Ejecuta los casos de clasificación del router contra el modelo configurado."""

import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.router.graph import graph  # noqa: E402

CASOS_PATH = ROOT / "tests" / "casos_router.json"


def cargar_casos() -> list[dict[str, str]]:
    with CASOS_PATH.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def recortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else f"{texto[:limite - 1]}…"


def main() -> None:
    load_dotenv(ROOT / ".env")
    if not os.getenv("GOOGLE_API_KEY"):
        raise SystemExit("Falta GOOGLE_API_KEY. Añádela a tu archivo .env local.")

    resultados: list[dict[str, Any]] = []
    for indice, caso in enumerate(cargar_casos(), start=1):
        state = graph.invoke(
            {"mensaje": caso["mensaje"]},
            config={"configurable": {"thread_id": f"script-router-{indice}"}},
        )
        resultados.append(
            {
                "mensaje": caso["mensaje"],
                "esperado": caso["esperado"],
                "obtenido": state["ruta"],
                "motivo": state["motivo"],
            }
        )

    encabezado = ("Mensaje", "Esperado", "Obtenido", "Resultado", "Motivo")
    print(" | ".join(encabezado))
    print(" | ".join("---" for _ in encabezado))
    for resultado in resultados:
        correcto = resultado["esperado"] == resultado["obtenido"]
        marca = "✔" if correcto else "✘"
        print(
            " | ".join(
                [
                    recortar(resultado["mensaje"], 45),
                    resultado["esperado"],
                    resultado["obtenido"],
                    marca,
                    recortar(resultado["motivo"], 70),
                ]
            )
        )

    aciertos = sum(r["esperado"] == r["obtenido"] for r in resultados)
    total = len(resultados)
    print(f"\nAciertos: {aciertos}/{total} ({aciertos / total:.0%})")

    fallados = [r for r in resultados if r["esperado"] != r["obtenido"]]
    if fallados:
        print("Fallados:")
        for resultado in fallados:
            print(
                f"- {resultado['mensaje']} "
                f"(esperado: {resultado['esperado']}, obtenido: {resultado['obtenido']})"
            )
    else:
        print("Fallados: ninguno")


if __name__ == "__main__":
    main()
