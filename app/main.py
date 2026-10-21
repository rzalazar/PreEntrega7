import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.worker import run_agent_job, get_job_status, set_job_status
from app.observability import setup_observability

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        setup_observability()
    except Exception as e:
        print(f"Observabilidad no disponible: {e}")
    yield

app = FastAPI(
    title="API REST Orquestador Multi-Agente Jerárquico",
    description="API Asíncrona con persistencia en Redis, Observabilidad Phoenix y HITL.",
    version="1.0.0",
    lifespan=lifespan,
)

class TaskRequest(BaseModel):
    query: str = Field(..., example="Investigar la adopción de LangGraph en empresas FinTech.")
    critical: Optional[bool] = Field(default=False, description="Marca si la tarea requiere aprobación humana explícita.")

class TaskResponse(BaseModel):
    job_id: str
    status: str
    message: str

class ApprovalRequest(BaseModel):
    approved: bool
    reason: Optional[str] = None

@app.post("/tasks", response_model=TaskResponse, status_code=202)
async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    
    # Detectar heurística de tarea crítica si contiene palabras sensibles
    is_critical = request.critical or any(w in request.query.lower() for w in ["publicar", "borrar", "eliminar"])
    
    await set_job_status(job_id, "PENDING")
    
    # Encolar ejecución asíncrona no bloqueante
    background_tasks.add_task(run_agent_job, job_id, request.query, is_critical, False)
    
    return TaskResponse(
        job_id=job_id,
        status="PENDING",
        message="Tarea encolada correctamente."
    )

@app.get("/tasks/{job_id}")
async def get_task_status(job_id: str):
    job_data = await get_job_status(job_id)
    if job_data.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail="El trabajo especificado no existe.")
    return job_data

@app.post("/tasks/{job_id}/approve", response_model=TaskResponse, status_code=200)
async def approve_task(job_id: str, request: ApprovalRequest, background_tasks: BackgroundTasks):
    job_data = await get_job_status(job_id)
    if job_data.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
        
    if job_data.get("status") != "WAITING_APPROVAL":
        raise HTTPException(status_code=400, detail=f"El trabajo no está esperando aprobación (Estado actual: {job_data.get('status')}).")
        
    if not request.approved:
        await set_job_status(job_id, "REJECTED", error="Rechazado por el operador humano.")
        return TaskResponse(job_id=job_id, status="REJECTED", message="Tarea rechazada.")

    # Reanudar la tarea en segundo plano sobre el mismo thread_id
    background_tasks.add_task(run_agent_job, job_id, "", False, True, True)
    
    return TaskResponse(
        job_id=job_id,
        status="RUNNING",
        message="Aprobación registrada. Reanudando ejecución del grafo."
    )