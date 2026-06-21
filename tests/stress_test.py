"""
Stress test para AI Service API.
Mide el tiempo de extremo a extremo: POST (submit) → GET /status done.

Uso:
    python3 stress_test.py [--jobs N] [--concurrency N] [--host URL]
"""

import asyncio
import argparse
import statistics
import time
from dataclasses import dataclass, field

import httpx

# ── Payloads de prueba por servicio ────────────────────────────────────────────

SCENARIOS = {
    "translation": [
        {"text": "The product is available in multiple colors and sizes.", "target_language": "español"},
        {"text": "Please contact our support team for further assistance.", "target_language": "francés"},
        {"text": "Your order has been confirmed and will be shipped soon.", "target_language": "portugués"},
    ],
    "product_qa": [
        {
            "context": "Laptop X500: Intel i7 12a gen, 16GB RAM DDR5, 512GB SSD NVMe, batería 10h, precio $1200.",
            "question": "¿Cuánta RAM tiene?",
        },
        {
            "context": "Smartphone Pro Max: pantalla AMOLED 6.7\", cámara 108MP, batería 5000mAh, precio $899.",
            "question": "¿Qué tipo de pantalla tiene?",
        },
        {
            "context": "Auriculares WirelessX: cancelación de ruido activa, autonomía 30h, carga rápida 15min=3h, precio $199.",
            "question": "¿Cuántas horas de batería tiene?",
        },
    ],
    "commercial_text": [
        {"text_type": "post", "product_description": "Café artesanal colombiano tostado en pequeños lotes con notas de chocolate."},
        {"text_type": "email", "product_description": "Software de gestión de inventario para pymes, fácil de usar, sin instalación."},
        {"text_type": "anuncio", "product_description": "Zapatillas deportivas de carbono para running, ultraligeras y resistentes."},
    ],
}

ENDPOINTS = {
    "translation": "/api/translate",
    "product_qa": "/api/qa/product",
    "commercial_text": "/api/generate/text",
}


# ── Estructuras de datos ───────────────────────────────────────────────────────

@dataclass
class JobResult:
    service: str
    job_id: str
    status: str
    elapsed: float        # segundos submit → done/error
    queue_wait: float     # segundos submit → processing
    process_time: float   # segundos processing → done/error
    error: str | None = None


@dataclass
class ServiceStats:
    service: str
    results: list[JobResult] = field(default_factory=list)

    def done(self):
        return [r for r in self.results if r.status == "done"]

    def errors(self):
        return [r for r in self.results if r.status == "error"]

    def times(self):
        return [r.elapsed for r in self.done()]

    def queue_times(self):
        return [r.queue_wait for r in self.done()]

    def process_times(self):
        return [r.process_time for r in self.done()]

    def percentile(self, data: list[float], p: int) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p / 100)
        return sorted_data[min(idx, len(sorted_data) - 1)]


# ── Lógica de un job individual ────────────────────────────────────────────────

async def run_job(
    client: httpx.AsyncClient,
    service: str,
    payload: dict,
    poll_interval: float = 0.5,
) -> JobResult:
    endpoint = ENDPOINTS[service]

    t_submit = time.perf_counter()
    resp = await client.post(endpoint, json=payload)
    resp.raise_for_status()
    job_id = resp.json()["job_id"]

    t_processing = None

    while True:
        await asyncio.sleep(poll_interval)
        status_resp = await client.get(f"/status/{job_id}")
        data = status_resp.json()
        current_status = data["status"]

        if current_status == "processing" and t_processing is None:
            t_processing = time.perf_counter()

        if current_status in ("done", "error"):
            t_done = time.perf_counter()
            elapsed = t_done - t_submit
            queue_wait = (t_processing - t_submit) if t_processing else elapsed
            process_time = (t_done - t_processing) if t_processing else 0.0
            return JobResult(
                service=service,
                job_id=job_id,
                status=current_status,
                elapsed=elapsed,
                queue_wait=queue_wait,
                process_time=process_time,
                error=data.get("error"),
            )


# ── Runner de stress test ──────────────────────────────────────────────────────

async def stress_test(host: str, total_jobs: int, concurrency: int, api_key: str) -> dict[str, ServiceStats]:
    services = list(SCENARIOS.keys())
    stats = {s: ServiceStats(service=s) for s in services}

    # Distribuir jobs entre servicios de forma balanceada
    jobs_per_service = total_jobs // len(services)
    job_queue: list[tuple[str, dict]] = []

    for service in services:
        payloads = SCENARIOS[service]
        for i in range(jobs_per_service):
            job_queue.append((service, payloads[i % len(payloads)]))

    total = len(job_queue)
    completed = 0
    semaphore = asyncio.Semaphore(concurrency)

    print(f"\n  Enviando {total} jobs ({jobs_per_service} por servicio) | concurrencia: {concurrency}")
    print(f"  Host: {host}  |  X-API-Key: {api_key[:8]}…\n")

    bar_width = 40

    async def bounded_job(service: str, payload: dict) -> JobResult:
        nonlocal completed
        async with semaphore:
            result = await run_job(client, service, payload)
        completed += 1
        pct = completed / total
        filled = int(bar_width * pct)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"\r  [{bar}] {completed}/{total}", end="", flush=True)
        return result

    async with httpx.AsyncClient(base_url=host, timeout=300.0, headers={"X-API-Key": api_key}) as client:
        t_start = time.perf_counter()
        results = await asyncio.gather(*[bounded_job(s, p) for s, p in job_queue])
        t_total = time.perf_counter() - t_start

    print()  # nueva línea tras la barra

    # Obtener métricas del scheduler desde el health check
    hc = httpx.get(f"{host}/").json()

    for r in results:
        stats[r.service].results.append(r)

    stats["_total_time"] = t_total          # type: ignore[assignment]
    stats["_swaps"] = hc.get("model_swaps", "?")  # type: ignore[assignment]
    return stats


# ── Reporte ────────────────────────────────────────────────────────────────────

def print_report(stats: dict, total_jobs: int, concurrency: int) -> None:
    t_total = stats.pop("_total_time")
    swaps = stats.pop("_swaps", "?")

    COL = 16
    SEP = "─" * 78

    print(f"\n{'═' * 78}")
    print(f"  STRESS TEST — RESULTADOS")
    print(f"{'═' * 78}")
    print(f"  Jobs totales : {total_jobs}   Concurrencia : {concurrency}   Tiempo total : {t_total:.1f}s")
    print(f"  Throughput   : {total_jobs / t_total:.2f} jobs/s   Swaps de modelo : {swaps}")
    print(f"{'═' * 78}\n")

    header = f"  {'Servicio':<22} {'Jobs':>5} {'OK':>5} {'Err':>5} {'Avg':>8} {'Min':>8} {'Max':>8} {'p95':>8}"
    print(header)
    print(f"  {SEP}")

    for service, s in stats.items():
        times = s.times()
        n_done = len(s.done())
        n_err = len(s.errors())
        if times:
            avg = statistics.mean(times)
            mn = min(times)
            mx = max(times)
            p95 = s.percentile(times, 95)
        else:
            avg = mn = mx = p95 = 0.0

        print(
            f"  {service:<22} {len(s.results):>5} {n_done:>5} {n_err:>5} "
            f"{avg:>7.1f}s {mn:>7.1f}s {mx:>7.1f}s {p95:>7.1f}s"
        )

    print(f"\n  {'─' * 60}")
    print("  DESGLOSE: tiempo en cola vs tiempo de procesamiento\n")
    print(f"  {'Servicio':<22} {'Cola avg':>10} {'Cola p95':>10} {'Proc avg':>10} {'Proc p95':>10}")
    print(f"  {SEP}")

    for service, s in stats.items():
        qt = s.queue_times()
        pt = s.process_times()
        print(
            f"  {service:<22} "
            f"{statistics.mean(qt) if qt else 0:>9.1f}s "
            f"{s.percentile(qt, 95):>9.1f}s "
            f"{statistics.mean(pt) if pt else 0:>9.1f}s "
            f"{s.percentile(pt, 95):>9.1f}s"
        )

    print(f"\n{'═' * 78}\n")

    # Errores detallados si los hay
    for service, s in stats.items():
        if s.errors():
            print(f"  ERRORES en {service}:")
            for r in s.errors():
                print(f"    job_id={r.job_id}  error={r.error}")
            print()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress test AI Service API")
    parser.add_argument("--jobs", type=int, default=9, help="Total de jobs a enviar (múltiplo de 3, default: 9)")
    parser.add_argument("--concurrency", type=int, default=3, help="Jobs en vuelo simultáneamente (default: 3)")
    parser.add_argument("--host", default="http://localhost:8000", help="URL base del servidor")
    parser.add_argument("--api-key", required=True, help="X-API-Key para autenticación")
    args = parser.parse_args()

    # Ajustar al múltiplo de 3 más cercano
    jobs = max(3, (args.jobs // 3) * 3)

    stats = asyncio.run(stress_test(args.host, jobs, args.concurrency, args.api_key))
    print_report(stats, jobs, args.concurrency)
