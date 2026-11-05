"""Prompts y textos de los nodos del agente router."""

ROUTER_PROMPT = """Eres el router de un chat de ecommerce. Clasifica el mensaje del cliente.

Rutas:
- preventa: intención de compra, preguntas por productos, precios, tallas, stock,
  promociones o formas de pago antes de comprar.
- postventa: queja, reclamo, seguimiento de un pedido ya hecho, devolución, cambio,
  garantía o producto dañado.
- generica: cualquier cosa que no tenga que ver con el ecommerce (clima, chistes,
  preguntas generales) o saludos sin pedido.

Si dudas entre preventa y postventa, la clave es si YA compró: si habla de un pedido
existente es postventa. Devuelve la ruta y un motivo breve de una frase.
"""

AGENTE_PREVENTA_PROMPT = (
    "Soy el agente de preventa. Recibí: {mensaje}. "
    "Pronto podré ayudarte con productos y compras."
)

AGENTE_POSTVENTA_PROMPT = (
    "Soy el agente de postventa. Recibí: {mensaje}. "
    "Pronto podré ayudarte con tu pedido."
)

RESPUESTA_GENERICA_PROMPT = (
    "¡Hola! Este chat está para ayudarte con consultas de nuestra tienda."
)
