import asyncio
import itertools
import uuid
import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends, Security

from app.models import (
    TranslationRequest,
    ProductQARequest,
    CommercialTextRequest,
    JobResponse,
    JobStatusResponse,
    LogsResponse,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyInfo,
)
from app.config import OLLAMA_URL, DEFAULT_MODEL
from app.core.auth import require_api_key, require_admin, generate_key, hash_key
from app.core import database as db
from app.core import model_registry as registry
from app.core.scheduler import ModelAwareScheduler
from app.router import route

scheduler = ModelAwareScheduler()
_seq = itertools.count()
jobs: dict[str, dict] = {}


OLLAMA_RETRY_INTERVAL = 30  # segundos


async def ollama_watcher():
    while True:
        await asyncio.sleep(OLLAMA_RETRY_INTERVAL)
        await registry.refresh()


async def worker():
    while True:
        model, job_id, service_name, payload = await scheduler.get()
        jobs[job_id]["status"] = "processing"
        await db.log_job_processing(job_id)
        try:
            result = await route(service_name, payload, model)
            jobs[job_id].update({"status": "done", **result})
            await db.log_job_done(job_id, result["response"])
        except Exception as exc:
            jobs[job_id].update({"status": "error", "error": str(exc)})
            await db.log_job_error(job_id, str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    await registry.refresh()
    worker_task = asyncio.create_task(worker())
    watcher_task = asyncio.create_task(ollama_watcher())
    yield
    worker_task.cancel()
    watcher_task.cancel()
    await db.close_pool()


app = FastAPI(title="AI Service API", version="1.0.0", lifespan=lifespan)


async def enqueue(service_name: str, payload: dict, model: str, priority: int) -> str:
    if model != DEFAULT_MODEL:
        priority = 3

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "priority": priority,
        "response": None,
        "model": model,
        "service": service_name,
    }
    await db.log_job_created(job_id, service_name, model, priority, payload)
    scheduler.put(priority, next(_seq), job_id, service_name, model, payload)
    return job_id


def _check_model(model: str, service: str) -> None:
    error = registry.validate(model, service)
    if error:
        raise HTTPException(status_code=422, detail=error)


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "AI Service API corriendo",
        "ollama_available": registry.is_available(),
        "default_model": DEFAULT_MODEL,
        "queue_size": scheduler.qsize(),
        "current_model": scheduler.current_model,
        "model_swaps": scheduler.swaps,
        "pending_by_model": scheduler.pending_by_model(),
    }


@app.get("/models")
async def list_models():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"No se pudo conectar a Ollama: {exc}")


@app.get("/models/{service}")
def models_for_service(service: str):
    if service not in ("translation", "product_qa", "commercial_text"):
        raise HTTPException(status_code=404, detail=f"Servicio desconocido: {service}")
    allowed = registry.allowed_for(service)
    all_m = registry.all_models()
    excluded = [name for name, tag in all_m.items() if tag != "text"]
    return {
        "service": service,
        "default_model": DEFAULT_MODEL,
        "allowed_models": sorted(allowed),
        "excluded_models": sorted(excluded),
    }


@app.post("/api/translate", response_model=JobResponse, status_code=202)
async def translate(req: TranslationRequest, _: dict = Security(require_api_key)):
    _check_model(req.model, "translation")
    payload = req.model_dump(exclude={"priority", "model"})
    job_id = await enqueue("translation", payload, req.model, req.priority)
    return JobResponse(job_id=job_id, status="pending", priority=jobs[job_id]["priority"], model=req.model)


@app.post("/api/qa/product", response_model=JobResponse, status_code=202)
async def product_qa(req: ProductQARequest, _: dict = Security(require_api_key)):
    _check_model(req.model, "product_qa")
    payload = req.model_dump(exclude={"priority", "model"})
    job_id = await enqueue("product_qa", payload, req.model, req.priority)
    return JobResponse(job_id=job_id, status="pending", priority=jobs[job_id]["priority"], model=req.model)


@app.post("/api/generate/text", response_model=JobResponse, status_code=202)
async def generate_text(req: CommercialTextRequest, _: dict = Security(require_api_key)):
    _check_model(req.model, "commercial_text")
    payload = req.model_dump(exclude={"priority", "model"})
    job_id = await enqueue("commercial_text", payload, req.model, req.priority)
    return JobResponse(job_id=job_id, status="pending", priority=jobs[job_id]["priority"], model=req.model)


@app.get("/status/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str, _: dict = Security(require_api_key)):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return JobStatusResponse(job_id=job_id, **job)


@app.get("/logs", response_model=LogsResponse)
async def get_logs(
    service: str | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: int | None = Query(default=None, ge=1, le=3),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: dict = Security(require_api_key),
):
    offset = (page - 1) * page_size
    total, rows = await db.get_logs(service, status, priority, page_size, offset)
    return LogsResponse(total=total, page=page, page_size=page_size, results=rows)


# ── Admin: gestión de API keys ─────────────────────────────────────────────────

@app.post("/admin/keys", response_model=ApiKeyCreated, status_code=201)
async def create_key(body: ApiKeyCreate, _: None = Depends(require_admin)):
    plain = generate_key()
    key_id = await db.create_api_key(body.name, hash_key(plain))
    keys = await db.list_api_keys()
    created_at = next(k["created_at"] for k in keys if k["id"] == key_id)
    return ApiKeyCreated(id=key_id, name=body.name, key=plain, created_at=created_at)


@app.get("/admin/keys", response_model=list[ApiKeyInfo])
async def list_keys(_: None = Depends(require_admin)):
    return await db.list_api_keys()


@app.delete("/admin/keys/{key_id}", status_code=200)
async def revoke_key(key_id: int, _: None = Depends(require_admin)):
    revoked = await db.deactivate_api_key(key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Key no encontrada o ya estaba desactivada")
    return {"detail": f"Key {key_id} desactivada"}
