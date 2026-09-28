"""
Ollama LLM service — extension point for local LLM inference.
Not mandatory for the first version; raises NotImplementedError if called without setup.
"""

import json
import logging
from typing import Any, Optional

import httpx

from app.services.llm.base import BaseLLMService

logger = logging.getLogger(__name__)


class OllamaLLMService(BaseLLMService):
    """Ollama local LLM integration (future extension)."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url
        self.model = model

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> dict[str, Any]:
        text = await self.generate_text(prompt, system_instruction)
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Ollama returned malformed JSON: {e}") from e

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_instruction:
            body["system"] = system_instruction

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=body)
            if response.status_code != 200:
                raise RuntimeError(f"Ollama error {response.status_code}: {response.text[:500]}")
            data = response.json()
        return data.get("response", "")
