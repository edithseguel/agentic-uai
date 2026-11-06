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

## Telegram

El webhook verifica `X-Telegram-Bot-Api-Secret-Token`, ignora los updates sin
texto y usa el `chat_id` como memoria del router. No se usa ninguna librería de
bot: la respuesta se envía con `httpx` a `sendMessage`.

1. Crea el bot con [@BotFather](https://t.me/BotFather), ejecutando `/newbot`.
   Copia el token y elige un secreto largo. Configúralos en Heroku:

   ```bash
   heroku config:set TELEGRAM_TOKEN='TOKEN_DE_BOTFATHER' TELEGRAM_SECRET='SECRETO_LARGO' --app TU_APP_HEROKU
   ```

2. Confirma que `PUBLIC_URL` contiene la URL HTTPS de Heroku, guarda los
   cambios y despliega tanto en GitHub como en Heroku:

   ```bash
   git add api/app.py scripts/set_webhook.py scripts/webhook_info.py README.md
   git commit -m "connect telegram webhook"
   git push origin main
   git push heroku main
   ```

3. Con `PUBLIC_URL` ya configurada en el entorno actual, registra el webhook y
   verifica su estado. Los scripts leen `.env`; para Heroku puedes exportar las
   mismas variables localmente sin subirlas al repositorio:

   ```bash
   source .venv/bin/activate
   python scripts/set_webhook.py
   python scripts/webhook_info.py
   ```

4. Escribe al bot estos seis mensajes y comprueba la ruta en los logs:

   ```text
   ¿tienen la polera azul en talla M?
   mi pedido 4521 llegó roto
   hola
   ¿cuánto cuesta el envío a Valparaíso?
   quiero devolver unas zapatillas
   ¿qué hora es en Tokio?
   ```

   ```bash
   heroku logs --tail --app TU_APP_HEROKU
   ```

   Las rutas esperadas son `preventa`, `postventa`, `generica`, `preventa`,
   `postventa` y `generica`, respectivamente.

5. Si el bot no responde, revisa que el webhook apunte por **HTTPS** a
   `/telegram`, que `TELEGRAM_SECRET` sea el mismo en Telegram y Heroku, y que
   `TELEGRAM_TOKEN` sea correcto.

### Prueba opcional antes de desplegar

Con la API local en marcha, crea un túnel HTTPS temporal:

```bash
cloudflared tunnel --url http://localhost:8000
```

Usa la URL HTTPS resultante como `PUBLIC_URL` en tu `.env` y ejecuta
`python scripts/set_webhook.py`.

## Variables de entorno

| Variable | Uso |
| --- | --- |
| `GOOGLE_API_KEY` | Credencial para invocar Gemini. |
| `MODELO` | Modelo Gemini usado por el router. |
| `TELEGRAM_TOKEN` | Token de BotFather usado para enviar respuestas con `sendMessage`. |
| `TELEGRAM_SECRET` | Secreto que Telegram envía en cada webhook para validarlo. |
| `PUBLIC_URL` | URL HTTPS pública para registrar el webhook. |
# agentic-uai
