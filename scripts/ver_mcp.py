"""Inspecciona las herramientas disponibles en el MCP de Shopify."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.router.mcp_shopify import herramientas_mcp, inicializar_mcp_shopify


def esquema_argumentos(herramienta: Any) -> dict[str, Any]:
    """Normaliza esquemas Pydantic y diccionarios de herramientas MCP."""
    esquema = herramienta.args_schema
    if isinstance(esquema, dict):
        return esquema
    return esquema.model_json_schema()


def argumentos_busqueda(herramienta: Any, texto: str) -> dict[str, str]:
    """Elige el argumento de búsqueda declarado por la herramienta remota."""
    esquema = esquema_argumentos(herramienta)
    propiedades = esquema.get("properties", {})
    for nombre in ("consulta", "query", "texto", "busqueda"):
        if nombre in propiedades:
            return {nombre: texto}
    requeridos = esquema.get("required", [])
    if requeridos:
        return {requeridos[0]: texto}
    return {}


def argumentos_pedidos(herramienta: Any) -> dict[str, int]:
    """Solicita hasta cinco pedidos usando el nombre de límite que expone el MCP."""
    esquema = esquema_argumentos(herramienta)
    propiedades = esquema.get("properties", {})
    for nombre in ("limite", "limit"):
        if nombre in propiedades:
            return {nombre: 5}
    return {}


def extraer_objetos(resultado: Any) -> list[dict[str, Any]]:
    """Convierte los bloques de texto MCP que contienen JSON en diccionarios."""
    bloques = resultado if isinstance(resultado, list) else [resultado]
    objetos: list[dict[str, Any]] = []
    for bloque in bloques:
        texto = bloque.get("text") if isinstance(bloque, dict) else None
        if not isinstance(texto, str):
            continue
        try:
            objeto = json.loads(texto)
        except json.JSONDecodeError:
            continue
        if isinstance(objeto, dict):
            objetos.append(objeto)
        elif isinstance(objeto, list):
            objetos.extend(item for item in objeto if isinstance(item, dict))
    return objetos


async def imprimir_pedidos(herramientas: dict[str, Any]) -> None:
    """Imprime los últimos pedidos, completando la nota desde su detalle si existe."""
    buscador = herramientas["buscar_pedidos"]
    pedidos = extraer_objetos(
        await buscador.ainvoke(argumentos_pedidos(buscador))
    )
    detalle = herramientas.get("obtener_pedido")
    for pedido in pedidos:
        nota = pedido.get("nota")
        if nota is None and detalle is not None:
            resultado = await detalle.ainvoke(
                {"numero_o_id": pedido.get("numero", pedido.get("id", ""))}
            )
            detalles = extraer_objetos(resultado)
            if detalles:
                nota = detalles[0].get("nota")
        print(
            f"{pedido.get('numero', 'sin número')} | "
            f"total: {pedido.get('total', 'sin total')} | "
            f"pago: {pedido.get('pago', 'sin estado')} | "
            f"nota: {nota or 'sin nota'}"
        )


async def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Consulta el MCP de Shopify.")
    parser.add_argument("consulta", nargs="?", help="Texto para buscar productos.")
    parser.add_argument(
        "--pedidos", action="store_true", help="Muestra los últimos cinco pedidos."
    )
    args = parser.parse_args()

    if not await inicializar_mcp_shopify():
        raise SystemExit("El MCP de Shopify no está disponible.")

    herramientas = {herramienta.name: herramienta for herramienta in herramientas_mcp()}
    if args.pedidos:
        herramienta = herramientas.get("buscar_pedidos")
        if herramienta is None:
            raise SystemExit("buscar_pedidos no está disponible en el MCP.")
        await imprimir_pedidos(herramientas)
        return

    if args.consulta:
        herramienta = herramientas.get("buscar_productos")
        if herramienta is None:
            raise SystemExit("buscar_productos no está disponible en el MCP.")
        print(
            await herramienta.ainvoke(
                argumentos_busqueda(herramienta, args.consulta)
            )
        )
        return

    for herramienta in herramientas.values():
        print(f"{herramienta.name}: {herramienta.description}")


if __name__ == "__main__":
    asyncio.run(main())
