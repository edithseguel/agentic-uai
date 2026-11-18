"""Consulta directamente el agente A2A de inteligencia de redes."""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.router.a2a_redes import preguntar_redes


def main() -> None:
    load_dotenv(ROOT / ".env")
    if len(sys.argv) < 2:
        raise SystemExit('Uso: python scripts/ver_redes.py "pregunta"')
    pregunta = " ".join(sys.argv[1:])
    print(asyncio.run(preguntar_redes(pregunta, "ver-redes")))


if __name__ == "__main__":
    main()
