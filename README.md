# Ecommerce Router API

Servicio en Python 3.12 para un chat de ecommerce. El agente LangGraph `router`
clasifica cada mensaje en una de tres rutas:

- `preventa`: productos, precios, tallas, stock, promociones o pagos antes de comprar.
- `postventa`: pedidos existentes, reclamos, devoluciones, cambios o garantías.
- `generica`: saludos sin pedido y consultas que no pertenecen a la tienda.

La API FastAPI mantiene la memoria del grafo por usuario (`thread_id`) y expone
documentación interactiva en `/docs`.

## Requisitos y configuración local

Se necesita Python 3.12 y una clave de Google AI. Crea el entorno e instala las
dependencias si aún no existen:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` localmente y completa al menos `GOOGLE_API_KEY`. No subas ese
archivo al repositorio.

## Ejecutar el router localmente

Con el entorno activado, ejecuta un mensaje y muestra los saltos del grafo:

```bash
python main.py router "¿tienen la polera azul en talla M?" --saltos
```

Para conservar conversación con un usuario específico:

```bash
python main.py router "mi pedido 4521 llegó roto" --saltos --thread-id cliente-123
```

Para imprimir el diagrama Mermaid sin invocar el modelo:

```bash
python main.py router --diagrama
```

## Levantar la API

```bash
source .venv/bin/activate
uvicorn api.app:app --reload --port 8000
```

Abre Swagger en [http://localhost:8000/docs](http://localhost:8000/docs).

Ejemplo para `/chat`:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"cliente-123","texto":"¿tienen la polera azul en talla M?"}'
```

La colección de Bruno está en `bruno/`. Selecciona el entorno `local` o cambia
la variable `baseUrl` para usar otro despliegue.

## Pruebas

Las pruebas del router llaman al modelo real, por lo que requieren
`GOOGLE_API_KEY` en `.env`.

```bash
source .venv/bin/activate
pytest
python scripts/test_router.py
```

El script imprime los 15 casos, la decisión, el motivo y la tasa de aciertos.
El test de pytest exige al menos 13 aciertos de 15.

## Desplegar en Heroku

El proyecto incluye `Procfile`, `.python-version` y `requirements.txt` para
Heroku. Reemplaza `TU_APP_HEROKU` por el nombre de tu aplicación; no incluyas
secretos en comandos que vayas a compartir.

```bash
heroku login
heroku create TU_APP_HEROKU
heroku git:remote -a TU_APP_HEROKU
heroku config:set GOOGLE_API_KEY='TU_CLAVE_LOCAL' MODELO='gemini-3.5-flash-lite' --app TU_APP_HEROKU
heroku config:set TELEGRAM_TOKEN='' TELEGRAM_SECRET='cambiame-por-un-secreto-largo' PUBLIC_URL='https://TU_APP_HEROKU.herokuapp.com' --app TU_APP_HEROKU
git push heroku main
heroku open --app TU_APP_HEROKU
```

Después de cambiar dependencias, actualiza el archivo que Heroku instala:

```bash
source .venv/bin/activate
python -m pip freeze > requirements.txt
```

## Conectar Telegram

1. Crea el bot con [@BotFather](https://t.me/BotFather) y copia su token en
   `TELEGRAM_TOKEN` (en `.env` local o `heroku config:set` en Heroku).
2. Elige un secreto largo para `TELEGRAM_SECRET` y define `PUBLIC_URL` con la
   URL HTTPS pública de Heroku.
3. Registra el webhook:

   ```bash
   curl -X POST "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook" \
     -d "url=$PUBLIC_URL/telegram" \
     -d "secret_token=$TELEGRAM_SECRET"
   ```

4. Comprueba la configuración:

   ```bash
   curl "https://api.telegram.org/bot$TELEGRAM_TOKEN/getWebhookInfo"
   ```

Actualmente `POST /telegram` solo confirma el JSON con `{"ok": true}`. La
validación del secreto, lectura de mensajes y envío de respuestas se añadirán
en la siguiente etapa de integración.

## Variables de entorno

| Variable | Uso |
| --- | --- |
| `GOOGLE_API_KEY` | Credencial para invocar Gemini. |
| `MODELO` | Modelo Gemini usado por el router. |
| `TELEGRAM_TOKEN` | Token de BotFather, reservado para la integración de Telegram. |
| `TELEGRAM_SECRET` | Secreto que Telegram enviará al webhook, reservado para su validación. |
| `PUBLIC_URL` | URL HTTPS pública para registrar el webhook. |
