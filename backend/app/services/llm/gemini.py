"""
Gemini LLM service — implements BaseLLMService using the Google Gemini REST API.
Uses httpx to call the API directly (no SDK dependency).
"""

import asyncio
import json
import logging
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.services.llm.base import BaseLLMService

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiLLMService(BaseLLMService):
    """Google Gemini API integration via REST."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set — LLM calls will fail")

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> dict[str, Any]:
        """Call Gemini and parse the response as JSON."""
        text = await self.generate_text(prompt, system_instruction)

        # Strip markdown fences if present
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
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Raw response: {text[:500]}")
            raise ValueError(f"LLM returned malformed JSON: {e}") from e

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        model_name = self.model
        if model_name.startswith("models/"):
            model_name = model_name[7:]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"


        body: dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 8192,
            },
        }

        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        max_retries = 2
        base_delay = 2  # seconds

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(max_retries + 1):
                response = await client.post(url, json=body)

                # Retry on transient errors (503 overloaded, 429 rate limit)
                if response.status_code in (503, 429) and attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # 2s, 4s, 8s
                    logger.warning(
                        f"Gemini API returned {response.status_code}, "
                        f"retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code != 200:
                    detail = response.text[:500]
                    logger.error(f"Gemini API error {response.status_code}: {detail}")
                    raise RuntimeError(
                        f"Gemini API returned status {response.status_code}: {detail}"
                    )

                data = response.json()
                break

        # Extract text from response
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in Gemini response")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise ValueError("No parts in Gemini response")
            return parts[0].get("text", "")
        except (KeyError, IndexError) as e:
            logger.error(f"Unexpected Gemini response structure: {e}")
            raise ValueError(f"Unexpected Gemini response: {e}") from e

