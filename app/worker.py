# app/worker.py
import os
import json
import asyncio
import traceback
import redis.asyncio as aioredis
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.types import Command
from app.graph import build_graph

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Lock para inicializar los índices de Redis solo una vez
_setup_lock = asyncio.Lock()
_setup_done = False

# (Gemini free tier ~15 RPM, 1 concurrentes × estar dentro del límite)
_agent_semaphore = asyncio.Semaphore(1)


async def _ensure_checkpointer_setup(checkpointer):
    global _setup_done
    if _setup_done:
        return
    async with _setup_lock:
        if _setup_done:
            return
        try:
            await checkpointer.asetup()
        except Exception as e:
            if "Index already exists" not in str(e):
                raise
        _setup_done = True


async def get_redis_client():
    return aioredis.from_url(REDIS_URL, decode_responses=True)


async def set_job_status(job_id, status, result=None, error=None):
    r = await get_redis_client()
    try:
        payload = {"status": status}
        if result is not None:
            payload["result"] = result
        if error is not None:
            payload["error"] = error
        await r.set(f"job:{job_id}", json.dumps(payload), ex=3600)
    finally:
        await r.close()


async def get_job_status(job_id):
    r = await get_redis_client()
    try:
        data = await r.get(f"job:{job_id}")
        if not data:
            return {"status": "NOT_FOUND"}
        return json.loads(data)
    finally:
        await r.close()


async def run_agent_job(job_id, query, is_critical=False, resume=False, approved=False):
    await set_job_status(job_id, "RUNNING")

    async with _agent_semaphore:
        try:
            async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
                await _ensure_checkpointer_setup(checkpointer)
                app_graph = build_graph(checkpointer=checkpointer)
                config = {"configurable": {"thread_id": job_id}}

                if resume:
                    input_data = Command(resume={"approved": approved})
                else:
                    input_data = {
                        "messages": [{"role": "user", "content": query}],
                        "next_agent": "Supervisor",
                        "research_data": None,
                        "analysis_data": None,
                        "step_count": 0,
                        "is_critical": is_critical,
                        "approved_by_human": False,
                    }

                async for _ in app_graph.astream(input_data, config=config, stream_mode="values"):
                    pass

                snapshot = await app_graph.aget_state(config)
                if snapshot.tasks and any(t.interrupts for t in snapshot.tasks):
                    await set_job_status(job_id, "WAITING_APPROVAL",
                        result={"message": "Esperando aprobación humana."})
                    return

                values = snapshot.values or {}
                await set_job_status(job_id, "DONE", result={
                    "research": values.get("research_data"),
                    "analysis": values.get("analysis_data"),
                })

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[worker] FAILED {job_id}: {tb}")
            await set_job_status(job_id, "FAILED", error=f"{type(e).__name__}: {e}")
        finally:
            await asyncio.sleep(20)