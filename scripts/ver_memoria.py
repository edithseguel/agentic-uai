"""Consulta los checkpoints persistidos por el router en PostgreSQL."""

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def crear_checkpointer() -> tuple[Any, Any]:
    """Abre un pool pequeño para inspeccionar, sin modificar los checkpoints."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("Falta DATABASE_URL; la memoria persistente no está configurada.")
    pool = ConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=2,
        timeout=5,
        check=ConnectionPool.check_connection,
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    return pool, PostgresSaver(pool)


def listar_hilos(checkpointer: Any) -> None:
    """Imprime cada hilo, su número de checkpoints y la fecha del último."""
    resumen: dict[str, dict[str, Any]] = defaultdict(lambda: {"cantidad": 0, "ultimo": ""})
    for checkpoint in checkpointer.list(None):
        thread_id = checkpoint.config["configurable"]["thread_id"]
        datos = resumen[thread_id]
        datos["cantidad"] += 1
        fecha = checkpoint.checkpoint.get("ts", "")
        if fecha > datos["ultimo"]:
            datos["ultimo"] = fecha

    if not resumen:
        print("No hay hilos guardados.")
        return
    print("Hilo | Checkpoints | Último checkpoint")
    print("--- | ---: | ---")
    for thread_id in sorted(resumen):
        datos = resumen[thread_id]
        print(f"{thread_id} | {datos['cantidad']} | {datos['ultimo']}")


def mostrar_hilo(checkpointer: Any, thread_id: str) -> None:
    """Imprime los mensajes acumulados en el checkpoint más reciente del hilo."""
    config = {"configurable": {"thread_id": thread_id}}
    checkpoint = next(checkpointer.list(config, limit=1), None)
    if checkpoint is None:
        print(f"No hay memoria guardada para el hilo '{thread_id}'.")
        return

    mensajes = checkpoint.checkpoint["channel_values"].get("messages", [])
    if not mensajes:
        print(f"El hilo '{thread_id}' no tiene mensajes.")
        return
    for mensaje in mensajes:
        tipo = getattr(mensaje, "type", "mensaje")
        contenido = getattr(mensaje, "content", str(mensaje))
        print(f"{tipo}: {contenido}")


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Muestra la memoria PostgreSQL del router.")
    parser.add_argument("thread_id", nargs="?", help="Hilo cuya conversación se desea ver.")
    args = parser.parse_args()

    pool, checkpointer = crear_checkpointer()
    try:
        if args.thread_id:
            mostrar_hilo(checkpointer, args.thread_id)
        else:
            listar_hilos(checkpointer)
    finally:
        pool.close()


if __name__ == "__main__":
    main()
