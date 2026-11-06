"""Muestra el estado y posibles errores pendientes del webhook de Telegram."""

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    load_dotenv(ROOT / ".env")
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise SystemExit("Falta la variable TELEGRAM_TOKEN.")

    response = httpx.get(
        f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=20.0
    )
    print(response.json())
    response.raise_for_status()


if __name__ == "__main__":
    main()
