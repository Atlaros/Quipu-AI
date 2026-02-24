"""Estado del agente LangGraph.

Define el TypedDict que representa el estado compartido entre todos
los nodos del grafo. LangGraph lo pasa automáticamente de nodo a nodo.
"""

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Estado del agente Quipu AI.

    Attributes:
        messages: Historial de mensajes (HumanMessage, AIMessage, ToolMessage).
                  add_messages se encarga de append automático.
    """

    messages: Annotated[list, add_messages]
