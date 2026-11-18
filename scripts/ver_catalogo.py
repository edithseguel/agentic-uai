"""Inspecciona el catálogo de productos sin modificar datos."""

import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.router.catalogo import CATALOGO_NO_DISPONIBLE, consultar_catalogo


def escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def imprimir_productos(texto: str) -> None:
    filas = consultar_catalogo(
        """
        SELECT nombre, precio_internet, rating
        FROM catalogo.productos_unicos
        WHERE LOWER(nombre) LIKE LOWER(%s) ESCAPE '\\'
        ORDER BY rating DESC NULLS LAST
        LIMIT 10
        """,
        [f"%{escapar_like(texto)}%"],
    )
    if filas == CATALOGO_NO_DISPONIBLE:
        print(CATALOGO_NO_DISPONIBLE)
        return
    for fila in filas:
        print(
            f"{fila['nombre']} | ${fila['precio_internet']} | rating: {fila['rating']}"
        )


def imprimir_categorias() -> None:
    filas = consultar_catalogo(
        """
        SELECT categoria, COUNT(*) AS cantidad
        FROM catalogo.productos_unicos
        GROUP BY categoria
        ORDER BY categoria
        """
    )
    if filas == CATALOGO_NO_DISPONIBLE:
        print(CATALOGO_NO_DISPONIBLE)
        return
    for fila in filas:
        print(f"{fila['categoria']}: {fila['cantidad']}")


def main() -> None:
    load_dotenv(ROOT / ".env")
    if len(sys.argv) > 1:
        imprimir_productos(" ".join(sys.argv[1:]))
    else:
        imprimir_categorias()


if __name__ == "__main__":
    main()
