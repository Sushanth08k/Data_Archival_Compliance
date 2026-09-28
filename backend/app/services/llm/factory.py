"""
LLM factory — returns the configured LLM service based on settings.
Supports: "regex" (default, deterministic), "gemini", "ollama".
"""

import logging
from app.core.config import settings
from app.services.llm.base import BaseLLMService
from app.services.llm.regex_service import RegexLLMService
from app.services.llm.gemini import GeminiLLMService
from app.services.llm.ollama import OllamaLLMService

logger = logging.getLogger(__name__)

_instance: BaseLLMService | None = None


def get_llm_service() -> BaseLLMService:
    """Return the singleton LLM service based on LLM_PROVIDER setting."""
    global _instance
    if _instance is None:
        provider = (settings.LLM_PROVIDER or "regex").lower()
        if provider == "regex":
            _instance = RegexLLMService()
        elif provider == "gemini":
            # If no API key or if configured for regex fallback
            if not settings.GEMINI_API_KEY:
                logger.warning("GEMINI_API_KEY is missing. Falling back to Regex rule engine.")
                _instance = RegexLLMService()
            else:
                _instance = GeminiLLMService()
        elif provider == "ollama":
            _instance = OllamaLLMService()
        else:
            logger.warning(f"Unknown LLM_PROVIDER: {provider}. Defaulting to Regex engine.")
            _instance = RegexLLMService()
    return _instance
