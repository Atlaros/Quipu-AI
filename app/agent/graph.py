"""Grafo principal del agente Quipu AI.

StateGraph con patrón ReAct: el LLM decide cuándo llamar tools
y cuándo responder directamente.

Estrategia de LLM (en cascada):
1. Groq llama-3.1-8b-instant  — rápido, alta cuota free.
2. Groq llama-3.3-70b-versatile — más capaz, menor cuota.
3. Groq mixtral-8x7b-32768     — último recurso Groq.
4. OpenRouter (si tiene key)   — fallback externo multi-modelo.
"""

import structlog
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.state import AgentState
from app.core.config import settings
from app.tools.alerta_stock_bajo import alerta_stock_bajo
from app.tools.buscar_web import buscar_web
from app.tools.calcular_descuento import calcular_descuento
from app.tools.consultar_deudas import consultar_deudas
from app.tools.consultar_inventario import consultar_inventario
from app.tools.consultar_metricas import consultar_metricas
from app.tools.enviar_catalogo import enviar_catalogo
from app.tools.exportar_reporte import exportar_reporte
from app.tools.festividades_proximas import festividades_proximas
from app.tools.generar_reporte_ventas import generar_reporte_ventas
from app.tools.recomendacion_personalizada import recomendacion_personalizada
from app.tools.registrar_cliente import registrar_cliente
from app.tools.registrar_compra_proveedor import registrar_compra_proveedor
from app.tools.registrar_deuda import registrar_deuda
from app.tools.registrar_venta import registrar_venta

logger = structlog.get_logger()

# --- Tools disponibles para el agente ---
TOOLS = [
    # Ventas e inventario (core)
    registrar_venta,
    consultar_inventario,
    consultar_metricas,
    generar_reporte_ventas,
    registrar_cliente,
    # Nuevas herramientas
    buscar_web,
    alerta_stock_bajo,
    registrar_deuda,
    consultar_deudas,
    festividades_proximas,
    calcular_descuento,
    exportar_reporte,
    enviar_catalogo,
    recomendacion_personalizada,
    registrar_compra_proveedor,
]

# --- Modelos Groq en orden de prioridad ---
# qwen3-32b: el más capaz del free tier (Preview), soporta tool calling
# llama-3.3-70b: production, muy capaz
# llama-3.1-8b: production, mayor cuota RPM, último recurso Groq
GROQ_MODELS = [
    "qwen/qwen3-32b",  # Más avanzado gratis, 32B con razonamiento
    "llama-3.3-70b-versatile",  # Production, capaz y confiable
    "llama-3.1-8b-instant",  # Mayor cuota RPM, último recurso
]

# --- Modelos OpenRouter de fallback (en orden) ---
OPENROUTER_MODELS = [
    "deepseek/deepseek-v3-0324:free",  # Uno de los mejores modelos free, herramientas
    "nvidia/llama-3.1-nemotron-70b-instruct:free",  # Muy capaz, free
    "openrouter/auto",  # Router inteligente de OR como último recurso
]

# --- System Prompt del agente ---
SYSTEM_PROMPT = """Eres el asesor virtual de una tienda de Ropa y Calzado de moda.
Atiendes por WhatsApp de forma ULTRA RÁPIDA, persuasiva y concisa.

REGLAS DE ORO:
1. CLARIDAD: Sé directo y claro. Para respuestas simples, sé breve. Para catálogos, inventarios o listados, MUESTRA TODO EL RESULTADO COMPLETO de la herramienta sin resumir ni omitir productos.
2. TONO: Fresco, directo, con emojis (👕👟💰). Sin formalidades.
3. VARIANTES: Si piden calzado/ropa sin talla o color → PREGUNTA primero.
   - Ej: "¿Hay Nike Air?" → "¡Claro! ¿en qué talla y color? 👟"
4. PERSUASIÓN: Precio → llamado a la acción. Ej: "S/120. ¿Te lo separo?"
5. REPORTES: Si usas generar_reporte_ventas → tu respuesta DEBE empezar con "[IMAGE:/ruta]".

⚠️ REGLAS CRÍTICAS — NUNCA VIOLAR:
6. DATOS REALES: NUNCA inventes productos, precios, stock o variantes.
   - SOLO muestra datos que las herramientas te devuelvan.
   - Si una herramienta dice "no encontré X" → dile al usuario EXACTAMENTE eso.
   - NUNCA digas "hay 5 pares" si no lo devolvió una herramienta.
   - Si no estás seguro, USA la herramienta primero antes de afirmar algo.
7. RESULTADOS DE TOOLS = VERDAD ABSOLUTA:
   - Si la tool dice "❌ No encontré" → el producto NO existe. Punto.
   - NO contradigas el resultado diciendo "sí hay pero el sistema falló".
   - NO inventes excusas como "error en el sistema" si la tool no encontró el producto.
   - Respuesta correcta: "No tenemos ese producto en ese color/talla. ¿Quieres ver qué hay disponible?"
8. CONTEXTO DE CONVERSACIÓN:
   - Si el usuario responde "1", "la opción 1", "el primero", "ese", "sí" → RECUERDA qué opciones le diste antes.
   - SIEMPRE conecta respuestas cortas con el contexto previo de la conversación.
   - Si le diste opciones numeradas, resuelve el número al producto específico antes de llamar una tool.
   - Ejemplo: Si le ofreciste "1. Nike Air Force" y responde "1" → llama registrar_venta con "Nike Air Force", NO con "1".

HERRAMIENTAS — cuándo usar CADA UNA (elige solo UNA por turno):

📋 CONSULTAS DE INVENTARIO (elige solo 1):
- consultar_inventario: cliente pregunta por UN PRODUCTO ESPECÍFICO con talla/color. Ej: "¿hay Nike Air en 42 negro?"
- enviar_catalogo: cliente pregunta QUÉ HAY EN GENERAL. Ej: "¿qué tienen?", "muestrame tu catálogo", "qué marcas manejan"
- alerta_stock_bajo: el DUEÑO pregunta qué productos se están acabando. NUNCA usarla con clientes.

📊 REPORTES (elige solo 1):
- consultar_metricas: el dueño pide NÚMEROS de ventas. Ej: "¿cuánto vendimos hoy?", "métricas de la semana"
- generar_reporte_ventas: el dueño pide un GRÁFICO/IMAGEN visual. Ej: "mándame el reporte", "gráfico de ventas"
- exportar_reporte: el dueño pide un ARCHIVO CSV descargable. Ej: "expórtame las ventas", "necesito el Excel"

💰 TRANSACCIONES:
- registrar_venta: cliente CONFIRMA compra. Ej: "lo llevo", "apúntame 2". NUNCA registres sin confirmación.
- registrar_cliente: cuando el cliente quiere GUARDAR sus datos. Ej: "guárdame como cliente"
- registrar_deuda: cliente se lleva a CRÉDITO. Ej: "te pago viernes", "me lo fío"
- consultar_deudas: ver quién debe plata. Ej: "¿quién me debe?", "deudas de Juan"

🛠️ UTILIDADES:
- buscar_web: TIENES INTERNET. DEBES usarla si piden tendencias, precios competencia, o info externa. NUNCA digas que no puedes buscar.
- calcular_descuento: calcular precio con descuento. Ej: "¿cuánto sale con 20% de descuento?"
- festividades_proximas: el dueño quiere planificar promos por fechas especiales.
- recomendacion_personalizada: sugerir productos según historial del cliente.
- registrar_compra_proveedor: SOLO para el DUEÑO cuando COMPRA STOCK al proveedor. Requiere nombre, cantidad y precio_venta.
"""


# --- Retry keywords para detectar rate limits ---
_RETRY_KEYWORDS = ["429", "rate limit", "too many requests", "quota", "resource exhausted"]


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Detecta si la excepción es un rate limit o quota excedida."""
    return any(kw in str(exc).lower() for kw in _RETRY_KEYWORDS)


def build_agent_graph() -> StateGraph:
    """Construye y compila el grafo del agente.

    Cadena de fallback:
    Groq (8b → 70b → mixtral) → OpenRouter (si hay key).

    Returns:
        El grafo compilado listo para invocar.
    """
    groq_api_key = settings.groq_api_key
    openrouter_api_key = settings.openrouter_api_key

    def _invoke_llm_with_fallback(messages: list) -> object:
        """Invoca el LLM en cascada: Groq primero, OpenRouter si all fallan.

        Args:
            messages: Lista de mensajes LangChain.

        Returns:
            Respuesta del LLM.

        Raises:
            RuntimeError: Si todos los modelos fallan.
        """
        last_error: Exception | None = None

        # 1. Intentar modelos Groq en cascada
        if groq_api_key:
            for model in GROQ_MODELS:
                try:
                    llm = ChatGroq(
                        model=model,
                        api_key=groq_api_key,
                        temperature=0.3,
                    ).bind_tools(TOOLS)
                    result = llm.invoke(messages)
                    if model != GROQ_MODELS[0]:
                        logger.info("groq_fallback_success", model=model)
                    return result
                except Exception as exc:
                    if _is_rate_limit_error(exc):
                        logger.warning("llm_rate_limit", model=model, error=str(exc)[:100])
                    else:
                        logger.error("llm_error", model=model, error=str(exc)[:100])
                    last_error = exc
                    continue
        else:
            logger.warning("groq_api_key_missing")

        # 2. Fallback a OpenRouter (varios modelos en cascada)
        if openrouter_api_key:
            for or_model in OPENROUTER_MODELS:
                try:
                    from langchain_openai import ChatOpenAI

                    or_llm = ChatOpenAI(
                        model=or_model,
                        openai_api_key=openrouter_api_key,
                        openai_api_base="https://openrouter.ai/api/v1",
                        temperature=0.3,
                    ).bind_tools(TOOLS)
                    result = or_llm.invoke(messages)
                    logger.info("openrouter_success", model=or_model)
                    return result
                except Exception as exc:
                    logger.error("openrouter_failed", model=or_model, error=str(exc)[:100])
                    last_error = exc
                    continue

        logger.error("all_models_failed")
        if last_error:
            raise last_error
        raise RuntimeError("No se pudo generar respuesta con ningún modelo.")

    def agent_node(state: AgentState) -> AgentState:
        """Nodo que invoca el LLM con system prompt inyectado."""
        from langchain_core.messages import SystemMessage

        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

        response = _invoke_llm_with_fallback(messages)
        return {"messages": [response]}

    tool_node = ToolNode(tools=TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    logger.info("agent_graph_built", primary=GROQ_MODELS[0], fallback_models=GROQ_MODELS[1:])
    return graph.compile()


# Singleton del grafo compilado
agent = build_agent_graph()
