"""Cliente A2A para consultar el agente externo de inteligencia de redes."""

import os

import httpx


async def preguntar_redes(texto: str, hilo: str) -> str:
    """Envía una consulta al agente de redes y devuelve su respuesta textual."""
    intel_url = os.getenv("INTEL_URL")
    intel_token = os.getenv("INTEL_TOKEN")
    if not intel_url or not intel_token:
        raise RuntimeError("Faltan INTEL_URL o INTEL_TOKEN.")

    from a2a.client import ClientConfig, create_client
    from a2a.helpers.proto_helpers import get_stream_response_text, new_text_message
    from a2a.types import Role, SendMessageRequest

    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {intel_token}"},
        timeout=60.0,
    ) as http:
        client = await create_client(
            intel_url,
            client_config=ClientConfig(httpx_client=http, streaming=False),
        )
        textos: list[str] = []
        async for respuesta in client.send_message(
            SendMessageRequest(
                message=new_text_message(
                    texto,
                    role=Role.ROLE_USER,
                    context_id=hilo,
                )
            )
        ):
            texto_respuesta = get_stream_response_text(respuesta)
            if texto_respuesta:
                textos.append(texto_respuesta)
        return "\n".join(textos).strip()
