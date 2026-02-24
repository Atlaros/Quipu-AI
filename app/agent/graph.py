"""Grafo principal del agente Quipu AI.

StateGraph con patrón ReAct: el LLM decide cuándo llamar tools
y cuándo responder directamente.

Incluye estrategia de Fallback robusta:
1. Intenta `gemini-2.0-flash`.
2. Si falla (quota/error), intenta `gemini-1.5-flash`.
3. Si falla, intenta `gemini-1.5-pro`.
4. Rota API Keys para cada modelo.
"""

import structlog
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.state import AgentState
from app.core.config import settings
from app.tools.consultar_inventario import consultar_inventario
from app.tools.consultar_metricas import consultar_metricas
from app.tools.generar_reporte_ventas import generar_reporte_ventas
from app.tools.registrar_cliente import registrar_cliente
from app.tools.registrar_venta import registrar_venta

logger = structlog.get_logger()

# --- Tools disponibles para el agente ---
TOOLS = [
    registrar_venta,
    consultar_inventario,
    consultar_metricas,
    generar_reporte_ventas,
    registrar_cliente,
]

# --- Modelos de fallback (en orden de prioridad) ---
# --- Modelos de fallback (en orden de prioridad) ---
FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]

# --- System Prompt del agente ---
SYSTEM_PROMPT = """Eres el asesor virtual de nuestra tienda de Ropa y Calzado de moda.
Tu objetivo es atender por WhatsApp de forma ULTRA RÁPIDA, persuasiva y concisa.

REGLAS DE ORO (CRÍTICO):
1. BREVEDAD: Tus respuestas deben tener MÁXIMO 1 o 2 líneas. NUNCA escribas párrafos. Responde al grano.
2. CERO FORMALIDADES: No digas "Estimado cliente" ni "Quedo atento". Usa tono fresco y emojis (👕👟).
3. VARIANTES OBLIGATORIAS: Si piden ropa/calzado y NO te dicen talla y/o color, PREGUNTA PRIMERO antes de consultar el stock.
   - Ej: "Hola, ¿hay Adidas Superstar?" -> Tú: "¡Hola! Claro, ¿en qué talla las buscas? 👟"
4. PERSUASIÓN: Si das un precio, incluye un llamado a la acción. Ej: "Están a S/120. ¿Te separo un par?"
5. REPORTES GRÁFICOS: Si usas la herramienta generar_reporte_ventas, esta te devolverá un texto como "[IMAGE:/ruta] texto". Tu respuesta FINAL al usuario DEBE comenzar EXACTAMENTE con ese bloque "[IMAGE:/ruta]". Es crítico, no pongas ninguna palabra antes.

HERRAMIENTAS:
1. registrar_venta: Solo cuando el cliente dice expresamente "lo compro", "apúntamelo", etc. Requiere Talla, Color, Precio.
2. consultar_inventario: Usa esto solo cuando ya sepas la talla que buscan.
3. consultar_metricas / generar_reporte_ventas: Solo para consultar métricas cuando los jefes te lo pidan.
"""

# --- Retry config para rate limits ---
_RETRY_KEYWORDS = ["429", "rate limit", "too many requests"]


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Detecta si la excepción es un rate limit de Groq."""
    error_msg = str(exc).lower()
    return any(kw.lower() in error_msg for kw in _RETRY_KEYWORDS)


def build_agent_graph() -> StateGraph:
    """Construye y compila el grafo del agente.

    Returns:
        El grafo compilado listo para invocar.

    Architecture:
        agent_node (LLM + tools) → tools_condition → tool_node → agent_node → END
    """
    # 1. API Keys disponibles
    api_key = settings.groq_api_key

    def _create_llm(model: str) -> ChatGroq:
        """Crea instancia del LLM con un modelo y key específicos."""
        llm = ChatGroq(
            model=model,
            api_key=api_key,
            temperature=0.3,
        )
        return llm.bind_tools(TOOLS)

    # 2. LLM invoke con estrategia de Fallback + Rotación de Keys
    def _invoke_llm_with_fallback(messages: list) -> object:
        """Invoca el LLM probando modelos y keys en cascada.

        Estrategia:
        Para cada modelo en FALLBACK_MODELS:
            Intenta invocar.
            Si éxito -> retorna.
            Si rate limit -> prueba siguiente modelo.

        Args:
            messages: Lista de mensajes.

        Returns:
            Respuesta del LLM.

        Raises:
            Exception: Si todos los modelos fallan.
        """
        last_error: Exception | None = None

        if not api_key:
            raise ValueError("Groq API Key no configurada, revisar variables de entorno.")

        for model in FALLBACK_MODELS:
            try:
                # logger.info("trying_llm", model=model)
                llm_with_tools = _create_llm(model)
                result = llm_with_tools.invoke(messages)
                
                if model != FALLBACK_MODELS[0]:
                    logger.info("fallback_success", model=model)
                
                return result

            except Exception as exc:
                if _is_rate_limit_error(exc):
                    logger.warning(
                        "llm_rate_limit",
                        model=model,
                        error=str(exc)[:100]
                    )
                    last_error = exc
                    continue
                
                # Si es otro error (ej. invalid argument), quizás el modelo no soporta algo
                # Logueamos y probamos siguiente (best effort)
                logger.error("llm_error", model=model, error=str(exc))
                last_error = exc
                continue

        # Todo falló
        logger.error("all_models_failed", attempts=len(FALLBACK_MODELS))
        if last_error:
            raise last_error
        msg = "No se pudo generar respuesta con ningún modelo."
        raise RuntimeError(msg)

    # 4. Nodo agente
    def agent_node(state: AgentState) -> AgentState:
        """Nodo que invoca el LLM."""
        from langchain_core.messages import SystemMessage

        messages = state["messages"]

        # Inyectar system prompt
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

        response = _invoke_llm_with_fallback(messages)
        return {"messages": [response]}

    # 5. Nodo tools
    tool_node = ToolNode(tools=TOOLS)

    # 6. Construir grafo
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    # 7. Edges
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    logger.info("agent_graph_built", fallback_models=FALLBACK_MODELS)

    return graph.compile()


# Singleton del grafo compilado
agent = build_agent_graph()
