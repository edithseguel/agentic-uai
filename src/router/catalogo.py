"""Acceso de solo lectura al catálogo de productos."""

import logging
import os
from typing import Any, Sequence

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)
CATALOGO_NO_DISPONIBLE = "catálogo no disponible"


def consultar_catalogo(
    consulta: str, parametros: Sequence[Any] = ()
) -> list[dict[str, Any]] | str:
    """Ejecuta un SELECT parametrizado y cierra la conexión al terminar."""
    if not consulta.lstrip().upper().startswith("SELECT"):
        raise ValueError("El catálogo solo admite consultas SELECT.")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.warning("No hay DATABASE_URL configurada para consultar el catálogo.")
        return CATALOGO_NO_DISPONIBLE

    try:
        with ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=1,
            timeout=5,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        ) as pool:
            with pool.connection() as conexion, conexion.cursor() as cursor:
                cursor.execute(consulta, tuple(parametros))
                return [dict(fila) for fila in cursor.fetchall()]
    except Exception as error:
        logger.warning("No fue posible consultar el catálogo (%s).", type(error).__name__)
        return CATALOGO_NO_DISPONIBLE
