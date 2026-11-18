"""Persistencia de reclamos para el agente de postventa."""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)
_reclamos_memoria: list[dict[str, Any]] = []
_usa_postgres = False

CREAR_TABLA_RECLAMOS = """
CREATE TABLE IF NOT EXISTS reclamos (
    ticket TEXT PRIMARY KEY,
    numero_pedido TEXT NOT NULL,
    motivo TEXT NOT NULL,
    detalle TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def _crear_pool() -> ConnectionPool | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None
    return ConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=1,
        timeout=5,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )


def inicializar_reclamos() -> bool:
    """Crea la tabla de reclamos al arrancar o habilita el respaldo en memoria."""
    global _usa_postgres
    pool = _crear_pool()
    if pool is None:
        _usa_postgres = False
        logger.warning("Reclamos en memoria: DATABASE_URL no está configurada.")
        return False

    try:
        with pool:
            with pool.connection() as conexion, conexion.cursor() as cursor:
                cursor.execute(CREAR_TABLA_RECLAMOS)
        _usa_postgres = True
        return True
    except Exception as error:
        _usa_postgres = False
        logger.warning(
            "Reclamos en memoria: no fue posible conectar a PostgreSQL (%s).",
            type(error).__name__,
        )
        return False


def crear_reclamo(
    numero_pedido: str, motivo: str, detalle: str, thread_id: str
) -> str:
    """Guarda un reclamo y devuelve su ticket, con respaldo temporal en memoria."""
    global _usa_postgres
    ticket = f"REC-{uuid.uuid4().hex[:8].upper()}"
    reclamo = {
        "ticket": ticket,
        "numero_pedido": numero_pedido,
        "motivo": motivo,
        "detalle": detalle,
        "thread_id": thread_id,
        "creado_en": datetime.now(timezone.utc),
    }

    if _usa_postgres or inicializar_reclamos():
        pool = _crear_pool()
        try:
            if pool is None:
                raise ConnectionError("DATABASE_URL no está configurada")
            with pool:
                with pool.connection() as conexion, conexion.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO reclamos
                            (ticket, numero_pedido, motivo, detalle, thread_id, creado_en)
                        VALUES (%(ticket)s, %(numero_pedido)s, %(motivo)s, %(detalle)s,
                                %(thread_id)s, %(creado_en)s)
                        """,
                        reclamo,
                    )
            return ticket
        except Exception as error:
            _usa_postgres = False
            logger.warning(
                "Reclamos en memoria: no fue posible guardar en PostgreSQL (%s).",
                type(error).__name__,
            )

    _reclamos_memoria.append(reclamo)
    return ticket


def listar_reclamos() -> list[dict[str, Any]]:
    """Lista los reclamos persistidos o los del respaldo en memoria."""
    if _usa_postgres or inicializar_reclamos():
        pool = _crear_pool()
        try:
            if pool is None:
                raise ConnectionError("DATABASE_URL no está configurada")
            with pool:
                with pool.connection() as conexion, conexion.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT ticket, numero_pedido, motivo, detalle, thread_id, creado_en
                        FROM reclamos
                        ORDER BY creado_en DESC
                        """
                    )
                    return [dict(fila) for fila in cursor.fetchall()]
        except Exception as error:
            logger.warning(
                "No fue posible listar reclamos en PostgreSQL (%s).",
                type(error).__name__,
            )
    return list(reversed(_reclamos_memoria))
