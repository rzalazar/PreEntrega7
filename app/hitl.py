from langgraph.types import interrupt
from app.state import TeamState

async def human_approval_node(state: TeamState) -> dict:
    """Nodo HITL: Interrumpe la ejecución si la tarea es crítica y aún no cuenta con aprobación."""
    is_critical = state.get("is_critical", False)
    approved = state.get("approved_by_human", False)
    
    if is_critical and not approved:
        # La función interrupt() pausa la ejecución y guarda el estado
        approval_decision = interrupt({
            "status": "WAITING_APPROVAL",
            "message": "Esta tarea requiere aprobación de un operador humano antes de ejecutar el análisis cuantitativo."
        })
        
        if approval_decision and approval_decision.get("approved"):
            return {"approved_by_human": True}
        else:
            raise Exception("Ejecución rechazada por el operador humano.")
            
    return {"approved_by_human": True}