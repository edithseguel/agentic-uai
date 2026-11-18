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
        if exc.name != f"src.{nombre_agente}.graph":
            raise
        raise SystemExit(f"No se encontró el agente '{nombre_agente}'.") from exc

    try:
        return modulo.graph
    except AttributeError as exc:
        raise SystemExit(
            f"El agente '{nombre_agente}' debe exponer un objeto 'graph' en graph.py."
        ) from exc


def mostrar_resultado(state: dict[str, Any]) -> None:
    """Imprime únicamente los datos útiles para quien ejecuta el agente."""
    print(
        {
            campo: state[campo]
            for campo in ("ruta", "motivo", "respuesta")
            if campo in state
        }
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Ejecuta un agente LangGraph.")
    parser.add_argument("nombre_agente")
    parser.add_argument("mensaje", nargs="?", help="Mensaje de entrada del agente.")
    parser.add_argument("--saltos", action="store_true", help="Muestra los nodos recorridos.")
    parser.add_argument(
        "--hilo",
        "--thread-id",
        dest="thread_id",
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

    inicializar = getattr(graph, "inicializar_memoria", None)
    cerrar = getattr(graph, "cerrar_memoria", None)
    if callable(inicializar):
        inicializar()
    try:
        entrada = {"mensaje": args.mensaje}
        config = {"configurable": {"thread_id": args.thread_id}}
        if args.saltos:
            ultimo_estado: dict[str, Any] = entrada
            subgrafos_anunciados: set[str] = set()
            for evento in graph.stream(entrada, config=config, stream_mode="updates"):
                namespace: tuple[str, ...] = ()
                paso = evento
                if (
                    isinstance(evento, tuple)
                    and len(evento) == 2
                    and isinstance(evento[0], tuple)
                ):
                    namespace, paso = evento
                if not isinstance(paso, dict):
                    continue
                for nodo, actualizacion in paso.items():
                    if namespace:
                        subgrafo = namespace[0].split(":", maxsplit=1)[0]
                        if nodo == "model" and subgrafo not in subgrafos_anunciados:
                            print(f"Nodo: {subgrafo}")
                            subgrafos_anunciados.add(subgrafo)
                        if nodo == "tools" and isinstance(actualizacion, dict):
                            for mensaje in actualizacion.get("messages", []):
                                if getattr(mensaje, "type", "") == "tool":
                                    sufijo = " (A2A)" if mensaje.name == "consultar_redes" else ""
                                    print(f"Herramienta: {mensaje.name}{sufijo}")
                        continue

                    if nodo not in subgrafos_anunciados:
                        print(f"Nodo: {nodo}")
                    if isinstance(actualizacion, dict):
                        ultimo_estado.update(actualizacion)
                        if nodo == "router" and "motivo" in actualizacion:
                            print(f"Motivo: {actualizacion['motivo']}")
            mostrar_resultado(ultimo_estado)
            return

        mostrar_resultado(graph.invoke(entrada, config=config))
    finally:
        if callable(cerrar):
            cerrar()


if __name__ == "__main__":
    main()
