# Guía para agentes

- Los agentes viven en `src/{nombre_agente}/` y contienen `graph.py`, `prompts.py` y `tools.py`.
- Cada nodo tiene su propio prompt en `prompts.py`. No se definen reglas ni prompts dentro de `graph.py`.
- Se ejecutan desde la raíz con `python main.py {nombre_agente} "mensaje"`.
- La bandera `--saltos` imprime los nodos por los que pasó el grafo.
- La bandera `--diagrama` imprime el Mermaid del grafo sin ejecutarlo.
- La API vive en `api/app.py` y se inicia con `uvicorn api.app:app --reload --port 8000`.
- Los scripts sueltos viven en `scripts/` y las pruebas en `tests/` (pytest).
- Para Heroku, mantener el `Procfile` con `web: uvicorn api.app:app --host 0.0.0.0 --port $PORT`, `.python-version` en `3.12` y `requirements.txt` siempre actualizado.
- No incluir valores reales de secretos ni credenciales en el código. Usar variables de entorno y `.env` local.
