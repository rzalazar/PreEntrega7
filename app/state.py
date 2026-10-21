from typing import TypedDict, Annotated, Optional, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TeamState(TypedDict):
    # Historial de conversación con reducer para acumular mensajes
    messages: Annotated[List[BaseMessage], add_messages]

    # Próximo agente a intervenir ("Investigador", "Analista" o "FINISH")
    next_agent: Optional[str]

    # Entregables específicos de cada especialista para evitar contaminación de contexto
    research_data: Optional[str]
    analysis_data: Optional[str]

    # Contador de iteraciones para prevenir el "Supervisor Infinito"
    step_count: int
    
    is_critical: bool
    # Bandera de aprobación para el flujo Human-in-the-loop (HITL)
    approved_by_human: bool