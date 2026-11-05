"""Ejecutor de agentes LangGraph desde la línea de comandos."""

import argparse
import importlib
import sys
from typing import Any

from dotenv import load_dotenv


def cargar_grafo(nombre_agente: str) -> Any:
    """Importa el grafo compilado definido por un agente."""
    try:
        modulo = importlib.import_module(f"src.{nombre_agente}.graph")
    except ModuleNotFoundError as exc:
        raise SystemExit(f"No se encontró el agente '{nombre_agente}'.") from exc

    try:
        return modulo.graph
    except AttributeError as exc:
        raise SystemExit(
            f"El agente '{nombre_agente}' debe exponer un objeto 'graph' en graph.py."
        ) from exc


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Ejecuta un agente LangGraph.")
    parser.add_argument("nombre_agente")
    parser.add_argument("mensaje", nargs="?", help="Mensaje de entrada del agente.")
    parser.add_argument("--saltos", action="store_true", help="Muestra los nodos recorridos.")
    parser.add_argument(
        "--thread-id",
        default="cli",
        help="Identificador del hilo para conservar la memoria del agente.",
    )
    parser.add_argument(
        "--diagrama", action="store_true", help="Imprime el diagrama Mermaid sin ejecutar el grafo."
    )
    args = parser.parse_args()

    graph = cargar_grafo(args.nombre_agente)
    if args.diagrama:
        print(graph.get_graph().draw_mermaid())
        return
    if args.mensaje is None:
        parser.error("mensaje es obligatorio salvo que se use --diagrama")

    entrada = {"mensaje": args.mensaje}
    config = {"configurable": {"thread_id": args.thread_id}}
    if args.saltos:
        ultimo_estado: dict[str, Any] = entrada
        for paso in graph.stream(entrada, config=config, stream_mode="updates"):
            for nodo, actualizacion in paso.items():
                print(f"Nodo: {nodo}")
                if isinstance(actualizacion, dict):
                    ultimo_estado.update(actualizacion)
                    if nodo == "router" and "motivo" in actualizacion:
                        print(f"Motivo: {actualizacion['motivo']}")
        print(ultimo_estado)
        return

    print(graph.invoke(entrada, config=config))


if __name__ == "__main__":
    main()
