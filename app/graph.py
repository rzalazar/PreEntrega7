import os
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

from app.state import TeamState
from app.config import get_llm

def _content_to_text(content) -> str:
    """Normaliza .content a string. Gemini 3.5 puede devolver lista de bloques."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif "text" in block:
                    parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p)
    return str(content)

# Esquema Pydantic unificado para la salida estructurada del Supervisor
class RouterSchema(BaseModel):
    next_agent: Literal["Investigador", "Analista", "FINISH"] = Field(
        description="El próximo agente que debe actuar o FINISH si la tarea está completada."
    )

async def supervisor_node(state: TeamState) -> dict:
    """Nodo Supervisor: Determina la ruta del flujo basándose en el estado actual y un límite de pasos."""
    llm = get_llm()
    messages = state.get("messages", [])
    step_count = state.get("step_count", 0) + 1
    
    # Prevenir bucles infinitos
    if step_count >= 6:
        return {"next_agent": "FINISH", "step_count": step_count}

    # FIX: cortar determinísticamente cuando ya hay research + analysis
    if state.get("research_data") and state.get("analysis_data"):
        print(f"[SUPERVISOR] step={step_count} research=True analysis=True -> FINISH (deterministic)")
        return {"next_agent": "FINISH", "step_count": step_count}
        
    system_prompt = (
        "Eres el Supervisor de un equipo jerárquico multi-agente. Tu rol es orquestar las tareas.\n"
        "- Delegar al 'Investigador' si falta buscar información de mercado o datos iniciales.\n"
        "- Delegar al 'Analista' si ya hay datos de investigación y se requiere cómputo/métricas cuantitativas.\n"
        "- Responder 'FINISH' cuando el análisis cuantitativo esté completo en el estado."
    )
    
    try:
        structured_llm = llm.with_structured_output(RouterSchema)
        response = await structured_llm.ainvoke([SystemMessage(content=system_prompt)] + messages)
        next_agent = response.next_agent
    except Exception:
        # Fallback determinista defensivo
        if not state.get("research_data"):
            next_agent = "Investigador"
        elif not state.get("analysis_data"):
            next_agent = "Analista"
        else:
            next_agent = "FINISH"
     
    print(f"[SUPERVISOR] step={step_count} research={bool(state.get('research_data'))} analysis={bool(state.get('analysis_data'))} -> next={next_agent}")
     
    return {"next_agent": next_agent, "step_count": step_count}

async def research_node(state: TeamState) -> dict:
    llm = get_llm()
    last_user_msg = state["messages"][0].content if state.get("messages") else "Investigar"
    prompt = f"Como Investigador de Mercado, investiga y provee datos clave, cifras y contexto sobre: {last_user_msg}"
    res = await llm.ainvoke([HumanMessage(content=prompt)])
    result_text = _content_to_text(res.content)
    print(f"[INVESTIGADOR] result_len={len(result_text)}")
    return {
        "research_data": result_text,
        "messages": [SystemMessage(content=f"[Investigación]: {result_text}")]
    }

async def human_approval_node(state: TeamState) -> dict:
    """Nodo HITL: Interrumpe la ejecución si la tarea es crítica y aún no cuenta con aprobación."""
    is_critical = state.get("is_critical", False)
    approved = state.get("approved_by_human", False)
    
    if is_critical and not approved:
        # La función interrupt() guarda el estado en el checkpointer de Redis y suspende la ejecución
        approval_decision = interrupt({
            "status": "WAITING_APPROVAL",
            "message": "Esta tarea requiere aprobación de un operador humano antes de ejecutar el análisis cuantitativo."
        })
        
        # Al reanudar con Command(resume=True) o update_state
        if approval_decision and approval_decision.get("approved"):
            return {"approved_by_human": True}
        else:
            raise Exception("Ejecución rechazada por el operador humano.")
            
    return {"approved_by_human": True}

async def analyst_node(state: TeamState) -> dict:
    llm = get_llm()
    research_context = state.get("research_data", "Sin contexto")
    prompt = (
        f"Basándote en estos datos de investigación:\n\n"
        f"{research_context[:2000]}\n\n"
        f"Calcula métricas cuantitativas, promedios y conclusiones clave."
    )
    res = await llm.ainvoke([HumanMessage(content=prompt)])
    result_text = _content_to_text(res.content)
    print(f"[ANALISTA] result_len={len(result_text)}")
    return {
        "analysis_data": result_text,
        "messages": [SystemMessage(content=f"[Análisis]: {result_text}")]
    }

def route_decision(state: TeamState) -> str:
    next_agent = state.get("next_agent")
    print(f"[ROUTE] next_agent={next_agent}")
    if next_agent == "Investigador":
        return "Investigador"
    elif next_agent == "Analista":
        return "AprobacionHumana"
    return END

def build_graph(checkpointer=None):
    workflow = StateGraph(TeamState)
    
    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("Investigador", research_node)
    workflow.add_node("AprobacionHumana", human_approval_node)
    workflow.add_node("Analista", analyst_node)
    
    workflow.set_entry_point("Supervisor")
    
    workflow.add_conditional_edges("Supervisor", route_decision, {
        "Investigador": "Investigador",
        "AprobacionHumana": "AprobacionHumana",
        END: END
    })
    
    workflow.add_edge("Investigador", "Supervisor")
    workflow.add_edge("AprobacionHumana", "Analista")
    workflow.add_edge("Analista", "Supervisor")
    
    return workflow.compile(checkpointer=checkpointer)