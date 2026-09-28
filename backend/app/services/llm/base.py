"""
LLM base interface — all LLM providers must implement this contract.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseLLMService(ABC):
    """
    Abstract base class for LLM integrations.
    The application calls generate_structured() and doesn't know
    whether Gemini, Ollama, or another provider is underneath.
    """

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Send a prompt to the LLM and return a parsed JSON dict.
        The implementation must handle:
          - sending the prompt
          - parsing the response as JSON
          - raising on malformed responses
        """
        ...

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """Send a prompt and return raw text."""
        ...
