from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from app.config import get_llm
from app.state import TeamState

def get_research_agent():
    """Crea un agente ReAct especializado en investigación y búsqueda web."""
    llm = get_llm(temperature=0.2)
    tools = [TavilySearchResults(max_results=3)]
    
    prompt = (        
        "Eres un Agente Especialista en Búsqueda e Investigación.\n"
        "Tu objetivo es consultar fuentes externas mediante tu herramienta de búsqueda para recopilar datos fácticos, "
        "noticias recientes, cifras y contexto objetivo sobre la consulta solicitada.\n"
        "Entrega resultados claros y resumidos enfocado únicamente en la información recopilada."
    )
# Se utiliza state_modifier para inyectar el System Prompt en create_react_agent
    return create_react_agent(model=llm, tools=tools, prompt=prompt)

def research_node(state: TeamState) -> dict:
    """Nodo del grafo que ejecuta la lógica del agente investigador."""
    user_query = state["messages"][0].content
    prompt_input = f"Investiga el mercado para la siguiente consulta: {user_query}"
    
    # Ejecutamos el agente ReAct con herramientas (el fallback a MockLLM se maneja desde config.py)
    agent = get_research_agent()
    result = agent.invoke({"messages": [HumanMessage(content=prompt_input)]})
    
    # Extraemos el contenido de la respuesta final del agente
    result_text = result["messages"][-1].content

    return {
        "messages": [HumanMessage(content=f"[INVESTIGADOR]: {result_text}", name="Investigador")],
        "research_data": result_text,
        "step_count": state.get("step_count", 0) + 1
    } 