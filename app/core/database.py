import json
import aiomysql
from app.config import DB_CONFIG

_pool: aiomysql.Pool | None = None


async def init_pool() -> None:
    global _pool
    _pool = await aiomysql.create_pool(**DB_CONFIG)


async def close_pool() -> None:
    if _pool:
        _pool.close()
        await _pool.wait_closed()


async def log_job_created(job_id: str, service: str, model: str, priority: int, payload: dict) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO job_logs (job_id, service, model, priority, payload, status) "
                "VALUES (%s, %s, %s, %s, %s, 'pending')",
                (job_id, service, model, priority, json.dumps(payload, ensure_ascii=False)),
            )


async def log_job_processing(job_id: str) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE job_logs SET status = 'processing' WHERE job_id = %s",
                (job_id,),
            )


async def log_job_done(job_id: str, response: str) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE job_logs SET status = 'done', response = %s WHERE job_id = %s",
                (response, job_id),
            )


async def log_job_error(job_id: str, error: str) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE job_logs SET status = 'error', error = %s WHERE job_id = %s",
                (error, job_id),
            )


async def get_logs(
    service: str | None,
    status: str | None,
    priority: int | None,
    limit: int,
    offset: int,
) -> tuple[int, list[dict]]:
    conditions = []
    params: list = []

    if service:
        conditions.append("service = %s")
        params.append(service)
    if status:
        conditions.append("status = %s")
        params.append(status)
    if priority is not None:
        conditions.append("priority = %s")
        params.append(priority)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(f"SELECT COUNT(*) AS total FROM job_logs {where}", params)
            total = (await cur.fetchone())["total"]

            await cur.execute(
                f"SELECT * FROM job_logs {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = await cur.fetchall()

    for row in rows:
        if isinstance(row.get("payload"), str):
            row["payload"] = json.loads(row["payload"])

    return total, rows


# ── API Keys ───────────────────────────────────────────────────────────────────

async def create_api_key(name: str, key_hash: str) -> int:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO api_keys (name, key_hash) VALUES (%s, %s)",
                (name, key_hash),
            )
            return cur.lastrowid


async def get_api_key_by_hash(key_hash: str) -> dict | None:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM api_keys WHERE key_hash = %s",
                (key_hash,),
            )
            return await cur.fetchone()


async def list_api_keys() -> list[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, name, is_active, created_at, last_used_at "
                "FROM api_keys ORDER BY created_at DESC"
            )
            return await cur.fetchall()


async def deactivate_api_key(key_id: int) -> bool:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE api_keys SET is_active = FALSE WHERE id = %s AND is_active = TRUE",
                (key_id,),
            )
            return cur.rowcount > 0


async def touch_api_key(key_id: int) -> None:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE api_keys SET last_used_at = NOW() WHERE id = %s",
                (key_id,),
            )
