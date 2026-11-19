"""Cliente MCP de Shopify y adaptadores para agentes síncronos o asíncronos."""

import asyncio
import logging
import os
import threading
from collections.abc import Awaitable
from typing import Any, TypeVar

from langchain_core.tools import StructuredTool
from langchain_core.runnables.config import var_child_runnable_config

logger = logging.getLogger(__name__)
NOMBRES_PERMITIDOS = {
    "buscar_productos",
    "obtener_producto",
    "listar_colecciones",
    "consultar_inventario",
    "crear_pedido",
}
TIENDA_NO_DISPONIBLE = "la tienda no está disponible por ahora"

_herramientas: dict[str, Any] = {}
_inicializado = False
_cliente: Any | None = None
T = TypeVar("T")


async def inicializar_mcp_shopify() -> bool:
    """Carga una vez las herramientas de Shopify sin impedir el arranque de la API."""
    global _cliente, _herramientas, _inicializado
    if _inicializado:
        return bool(_herramientas)
    _inicializado = True

    mcp_url = os.getenv("MCP_URL")
    mcp_token = os.getenv("MCP_AUTH_TOKEN")
    if not mcp_url or not mcp_token:
        logger.warning("MCP Shopify no disponible: faltan MCP_URL o MCP_AUTH_TOKEN.")
        return False

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        _cliente = MultiServerMCPClient(
            {
                "shopify": {
                    "transport": "streamable_http",
                    "url": mcp_url,
                    "headers": {"Authorization": f"Bearer {mcp_token}"},
                }
            }
        )
        herramientas = await _cliente.get_tools()
        _herramientas = {herramienta.name: herramienta for herramienta in herramientas}
        logger.info(
            "MCP Shopify conectado con %s herramientas.", len(_herramientas)
        )
        return True
    except Exception as error:
        logger.warning(
            "MCP Shopify no disponible al arrancar (%s).",
            type(error).__name__,
        )
        return False


def herramientas_mcp() -> list[Any]:
    """Devuelve todas las herramientas cargadas, para inspección desde terminal."""
    return list(_herramientas.values())


def _ejecutar_corutina_sincrona(corutina: Awaitable[T]) -> T:
    """Ejecuta una coroutine aun cuando la invocación síncrona tenga un loop activo."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(corutina)

    resultado: list[T] = []
    error: list[BaseException] = []

    def ejecutar() -> None:
        try:
            resultado.append(asyncio.run(corutina))
        except BaseException as excepcion:
            error.append(excepcion)

    hilo = threading.Thread(target=ejecutar, daemon=True)
    hilo.start()
    hilo.join()
    if error:
        raise error[0]
    return resultado[0]


def _preparar_argumentos(herramienta: Any, argumentos: dict[str, Any]) -> dict[str, Any]:
    """Completa de forma segura los campos obligatorios de un pedido de prueba."""
    if herramienta.name != "crear_pedido":
        return argumentos

    config = var_child_runnable_config.get() or {}
    hilo = str(config.get("configurable", {}).get("thread_id", "sin-hilo"))
    argumentos = dict(argumentos)
    argumentos["de_prueba"] = True
    argumentos["pagado"] = False
    argumentos.pop("email_cliente", None)
    argumentos["etiquetas"] = ["curso", "agente-preventa"]
    argumentos["nota"] = hilo
    return argumentos


def _adaptar_herramienta(herramienta: Any) -> StructuredTool:
    """Conserva ainvoke y añade invoke seguro para el grafo síncrono."""

    def invocar_sync(**argumentos: Any) -> Any:
        try:
            argumentos = _preparar_argumentos(herramienta, argumentos)
            return _ejecutar_corutina_sincrona(herramienta.ainvoke(argumentos))
        except Exception:
            return TIENDA_NO_DISPONIBLE

    async def invocar_async(**argumentos: Any) -> Any:
        try:
            argumentos = _preparar_argumentos(herramienta, argumentos)
            return await herramienta.ainvoke(argumentos)
        except Exception:
            return TIENDA_NO_DISPONIBLE

    return StructuredTool.from_function(
        func=invocar_sync,
        coroutine=invocar_async,
        name=herramienta.name,
        description=herramienta.description,
        args_schema=herramienta.args_schema,
    )


def herramientas_preventa_shopify() -> list[StructuredTool]:
    """Entrega al agente solo las operaciones Shopify autorizadas."""
    return [
        _adaptar_herramienta(herramienta)
        for nombre, herramienta in _herramientas.items()
        if nombre in NOMBRES_PERMITIDOS
    ]
