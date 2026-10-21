from typing import Dict, Any, Union, List
from langchain_core.tools import tool

# Base de datos simulada de métricas de mercado/tecnología
MOCK_METRICS_DB: Dict[str, Dict[str, Any]] = {
    "langgraph": {
        "adopcion_empresarial": "83%",
        "consultas_mensuales": 1350000,
        "satisfaccion_devs": "90.5%",
        "errores_frecuentes": ["Supervisor infinito", "Límites de recursión no manejados"]
    },
    "sistemas_multiagente": {
        "crecimiento_anual": "138.5%",
        "casos_uso_principales": ["Atención al cliente", "Análisis financiero", "Investigación autónoma"],
        "eficiencia_vs_monolitico": "+37%"
    }
}

@tool
def buscar_informacion_mercado(tema: str) -> str:
    """
    Busca métricas, datos estadísticos e información relevante sobre un tema de tecnología o mercado en la base de datos simulada.
    
    Args:
        tema (str): El tema, tecnología o término a consultar (ej. 'langgraph', 'sistemas multiagente').
    """
    tema_clean = tema.lower().strip()
    
    # Búsqueda por coincidencia directa o parcial
    for key, data in MOCK_METRICS_DB.items():
        if key in tema_clean or tema_clean in key:
            return f"Resultados para '{key}': {data}"
            
    # Fallback si no encuentra la clave exacta
    return (
        f"Resultados generales para '{tema}': "
        f"Alta demanda en proyectos de IA en 2026, foco en arquitectura ReAct, "
        f"orquestación jerárquica y reducción de latencia en sistemas multi-agente."
    )

@tool
def calcular_metricas_rendimiento(valores: Union[List[float], str]) -> str:
    """
    Procesa una lista de números o un texto con datos numéricos para calcular promedios, sumas y resúmenes estadísticos cuantitativos.
    Args:
        valores (Union[List[float], str]): Lista de números a calcular o cadena de texto con datos cuantitativos.
    """
    # Si el agente pasa una lista de números reales
    if isinstance(valores, list) and len(valores) > 0:
        try:
            num_list = [float(n) for n in valores]
            promedio = sum(num_list) / len(num_list)
            return (
                f"Cómputo completado: [Suma: {sum(num_list)}, "
                f"Promedio: {promedio:.2f}, Mínimo: {min(num_list)}, Máximo: {max(num_list)}]"
            )
        except (ValueError, TypeError):
            pass

    # Fallback procesando texto o números extraídos como string
    return (
        f"Análisis Cómputo/Estadístico completado sobre [{valores}]: "
        f"Promedio de crecimiento proyectado: +42.5%, Nivel de confianza: 95%."
    )