"""Herramientas de catálogo y postventa para los agentes del router."""

import asyncio
import json
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from langchain_core.runnables.config import var_child_runnable_config

from src.router.catalogo import consultar_catalogo
from src.router.a2a_redes import preguntar_redes
from src.router.reclamos import crear_reclamo as guardar_reclamo

VISTA_PRODUCTOS = "catalogo.productos_unicos"
RESUMEN_COLUMNAS = """
    sku_id, nombre, marca, precio_internet, descuento_pct, rating, link
"""


def escapar_like(texto: str) -> str:
    """Escapa comodines para que cada palabra se busque literalmente."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@tool
def buscar_productos(
    consulta: str,
    categoria: str | None = None,
    marca: str | None = None,
    precio_max: int | None = None,
) -> list[dict[str, Any]] | str:
    """Busca hasta cinco productos del catálogo por nombre, filtros y presupuesto."""
    palabras = [palabra for palabra in consulta.split() if palabra]
    if not palabras:
        return []

    filtros = ["TRUE"]
    parametros: list[Any] = []
    for palabra in palabras:
        filtros.append("LOWER(nombre) LIKE LOWER(%s) ESCAPE '\\'")
        parametros.append(f"%{escapar_like(palabra)}%")

    if categoria:
        filtros.append("categoria = %s")
        parametros.append(categoria)
    if marca:
        filtros.append("(LOWER(marca) LIKE LOWER(%s) ESCAPE '\\' OR LOWER(nombre) LIKE LOWER(%s) ESCAPE '\\')")
        patron_marca = f"%{escapar_like(marca)}%"
        parametros.extend([patron_marca, patron_marca])
    if precio_max is not None:
        filtros.append("precio_internet <= %s")
        parametros.append(precio_max)

    return consultar_catalogo(
        f"""
        SELECT {RESUMEN_COLUMNAS}
        FROM {VISTA_PRODUCTOS}
        WHERE {' AND '.join(filtros)}
        ORDER BY rating DESC NULLS LAST
        LIMIT 5
        """,
        parametros,
    )


@tool
def ver_producto(sku_id: str) -> list[dict[str, Any]] | str:
    """Obtiene el detalle y enlace de un producto a partir de su SKU."""
    return consultar_catalogo(
        f"""
        SELECT sku_id, nombre, marca, categoria, subcategoria, precio_normal,
               precio_internet, descuento_pct, rating, tienda_oficial, link, imagen
        FROM {VISTA_PRODUCTOS}
        WHERE sku_id = %s
        LIMIT 1
        """,
        [sku_id],
    )


@tool
def mejores_ofertas(
    categoria: str | None = None, limite: int = 5
) -> list[dict[str, Any]] | str:
    """Devuelve hasta cinco productos con mayor descuento del catálogo."""
    limite_seguro = max(1, min(limite, 5))
    filtros = ["descuento_pct IS NOT NULL"]
    parametros: list[Any] = []
    if categoria:
        filtros.append("categoria = %s")
        parametros.append(categoria)

    return consultar_catalogo(
        f"""
        SELECT {RESUMEN_COLUMNAS}
        FROM {VISTA_PRODUCTOS}
        WHERE {' AND '.join(filtros)}
        ORDER BY descuento_pct DESC, rating DESC NULLS LAST
        LIMIT %s
        """,
        [*parametros, limite_seguro],
    )


ROOT = Path(__file__).resolve().parents[2]
PEDIDOS_PATH = ROOT / "data" / "pedidos.json"
POLITICAS_PATH = ROOT / "data" / "politicas.md"


def _thread_id_actual() -> str:
    """Obtiene el hilo de LangGraph sin exponerlo como argumento de la herramienta."""
    config = var_child_runnable_config.get() or {}
    return str(config.get("configurable", {}).get("thread_id", "sin-hilo"))


@tool
def consultar_redes(tema: str) -> str:
    """Consulta opiniones, noticias y tendencias externas sobre una marca o producto."""
    try:
        respuesta = asyncio.run(preguntar_redes(tema, _thread_id_actual()))
        return respuesta[:1500]
    except Exception:
        return "el agente de redes no está disponible"


PREVENTA_TOOLS = [
    buscar_productos,
    ver_producto,
    mejores_ofertas,
    consultar_redes,
]


@tool
def estado_pedido(numero: str) -> dict[str, Any] | str:
    """Busca un pedido por su número y devuelve su información o 'no existe'."""
    try:
        pedidos = json.loads(PEDIDOS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "no existe"
    for pedido in pedidos:
        if pedido["numero"].casefold() == numero.casefold():
            return pedido
    return "no existe"


@tool
def politica(tema: str) -> str:
    """Devuelve la política de devoluciones, cambios o garantía solicitada."""
    secciones = {
        "devolucion": "devoluciones",
        "devoluciones": "devoluciones",
        "cambio": "cambios",
        "cambios": "cambios",
        "garantia": "garantía",
        "garantía": "garantía",
    }
    clave = secciones.get(tema.strip().casefold())
    if clave is None:
        return "No existe una política para ese tema."

    try:
        contenido = POLITICAS_PATH.read_text(encoding="utf-8")
    except OSError:
        return "No existe una política para ese tema."

    encabezado = f"## {clave.capitalize()}"
    seccion = contenido.split(encabezado, maxsplit=1)
    if len(seccion) != 2:
        return "No existe una política para ese tema."
    return seccion[1].split("\n## ", maxsplit=1)[0].strip()


@tool
def crear_reclamo(numero_pedido: str, motivo: str, detalle: str) -> str:
    """Crea un reclamo confirmado por el cliente y devuelve su número de ticket."""
    ticket = guardar_reclamo(numero_pedido, motivo, detalle, _thread_id_actual())
    return f"Reclamo creado. Ticket: {ticket}"


POSTVENTA_TOOLS = [estado_pedido, politica, crear_reclamo]
