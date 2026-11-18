"""Lista los reclamos almacenados para revisión local."""

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.router.reclamos import inicializar_reclamos, listar_reclamos


def main() -> None:
    load_dotenv(ROOT / ".env")
    inicializar_reclamos()
    reclamos = listar_reclamos()
    if not reclamos:
        print("No hay reclamos.")
        return
    for reclamo in reclamos:
        print(
            f"{reclamo['ticket']} | pedido: {reclamo['numero_pedido']} | "
            f"motivo: {reclamo['motivo']} | hilo: {reclamo['thread_id']} | "
            f"fecha: {reclamo['creado_en']}"
        )


if __name__ == "__main__":
    main()
