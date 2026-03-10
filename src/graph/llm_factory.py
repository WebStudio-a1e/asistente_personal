"""LLM Factory — retorna el LLM correcto según la variable de entorno del agente.

Cambiar el LLM de un agente = cambiar una variable de entorno. Sin tocar código.

Modelos soportados:
  claude-*    → ChatAnthropic
  gpt-*       → ChatOpenAI
  gemini-*    → ChatGoogleGenerativeAI
  deepseek-*  → ChatOpenAI (base_url DeepSeek)
"""

import os

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

_AGENT_ENV: dict[str, str] = {
    "orchestrator": "LLM_ORCHESTRATOR",
    "tasks":        "LLM_TASKS",
    "ideas":        "LLM_IDEAS",
    "agenda":       "LLM_AGENDA",
    "accounting":   "LLM_ACCOUNTING",
    "reporting":    "LLM_REPORTING",
}


def get_llm(agent_name: str):
    """Retorna el LLM configurado para el agente indicado.

    Args:
        agent_name: nombre del agente (orchestrator, tasks, ideas,
                    agenda, accounting, reporting).

    Raises:
        ValueError: agente desconocido o modelo no soportado.
        RuntimeError: variable de entorno no definida o vacía.
    """
    env_var = _AGENT_ENV.get(agent_name)
    if env_var is None:
        raise ValueError(
            f"Agente desconocido: '{agent_name}'. "
            f"Válidos: {list(_AGENT_ENV)}"
        )

    model = os.environ.get(env_var, "").strip()
    if not model:
        raise RuntimeError(
            f"Variable de entorno requerida no definida o vacía: {env_var}"
        )

    if model.startswith("claude"):
        return ChatAnthropic(model=model)

    if model.startswith("gpt"):
        return ChatOpenAI(model=model)

    if model.startswith("gemini"):
        return ChatGoogleGenerativeAI(model=model)

    if model.startswith("deepseek"):
        return ChatOpenAI(
            model=model,
            base_url="https://api.deepseek.com",
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        )

    raise ValueError(
        f"Modelo no soportado: '{model}'. "
        "Prefijos válidos: claude-*, gpt-*, gemini-*, deepseek-*"
    )
