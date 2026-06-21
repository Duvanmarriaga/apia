# APIA

API gateway en FastAPI para exponer servicios de IA (traducción, Q&A de producto, generación de texto comercial) sobre un servidor [Ollama](https://ollama.com/) local, con cola de jobs asíncrona y autenticación por API key.

## Por qué existe

Ollama solo puede atender un modelo a la vez en GPU sin pagar el costo de un swap (~5s en una RTX 3050 8GB). En lugar de dejar que las peticiones compitan libremente, todo pasa por una cola (`ModelAwareScheduler`) que agrupa los jobs por modelo activo y minimiza los cambios de contexto en VRAM, con prioridad para el modelo por defecto que se mantiene caliente.

## Arquitectura

```
POST /api/*  →  enqueue()  →  ModelAwareScheduler  →  worker()  →  router.route()  →  BaseService.run()  →  Ollama
```

- Las peticiones se encolan y devuelven un `job_id` (202 Accepted); el cliente hace polling a `/status/{job_id}`.
- Un único worker consume la cola hacia Ollama, evitando saturar la GPU.
- Cada job y cada API key se persisten en MySQL (`job_logs`, `api_keys`); las keys se guardan como hash SHA-256.
- `model_registry` cachea los modelos disponibles en Ollama y los clasifica como `text`/`code`, rechazando modelos de código en los servicios de texto.

## Stack

FastAPI · aiomysql · httpx · Ollama · Docker

## Levantar el proyecto

```bash
cp .env.example .env   # completar con tus credenciales
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

O con Docker:

```bash
docker compose up --build
```

## Uso

```bash
# Crear una API key de aplicación
curl -X POST http://localhost:8000/admin/keys \
  -H "X-Admin-Key: <ADMIN_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"name": "mi-app"}'

# Encolar una traducción
curl -X POST http://localhost:8000/api/translate \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "target_lang": "es", "model": "llama3.2:3b"}'

# Consultar estado del job
curl http://localhost:8000/status/<job_id> -H "X-API-Key: <key>"
```

## Tests

```bash
python3 tests/stress_test.py --jobs 18 --concurrency 6 --api-key <key> --host http://localhost:8000
```

Mide tiempos extremo a extremo (submit → done) bajo carga concurrente.
