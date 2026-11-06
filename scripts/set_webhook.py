"""Registra el webhook de Telegram en la URL pública configurada."""

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Falta la variable {name}.")
    return value


def main() -> None:
    load_dotenv(ROOT / ".env")
    token = required("TELEGRAM_TOKEN")
    secret = required("TELEGRAM_SECRET")
    public_url = required("PUBLIC_URL").rstrip("/")

    response = httpx.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        json={"url": f"{public_url}/telegram", "secret_token": secret},
        timeout=20.0,
    )
    print(response.json())
    response.raise_for_status()


if __name__ == "__main__":
    main()
