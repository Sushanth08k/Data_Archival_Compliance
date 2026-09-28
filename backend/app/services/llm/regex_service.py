"""
Regex LLM service implementation — implements BaseLLMService interface
using deterministic regex and heuristic policy rule extraction instead of an external API.
"""

import json
import logging
from typing import Any, Optional

from app.services.llm.base import BaseLLMService
from app.services.policies.regex_extractor import extract_policy_with_regex

logger = logging.getLogger(__name__)


class RegexLLMService(BaseLLMService):
    """
    Regex-based policy analyzer that satisfies the BaseLLMService interface.
    Extracts structured compliance rules without external API calls or tokens.
    """

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Extract policy text from the prompt and return the structured JSON dict.
        """
        logger.info("Executing Regex-based policy extraction engine...")

        # Extract text between markers if present
        text = prompt
        if "--- POLICY DOCUMENT START ---" in prompt and "--- POLICY DOCUMENT END ---" in prompt:
            text = prompt.split("--- POLICY DOCUMENT START ---")[1].split("--- POLICY DOCUMENT END ---")[0]

        result = extract_policy_with_regex(text)
        logger.info(
            f"Regex extraction completed: {len(result.get('rules', []))} rules, "
            f"{len(result.get('exceptions', []))} exceptions extracted."
        )
        return result

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """Return a formatted JSON string summary."""
        structured = await self.generate_structured(prompt, system_instruction)
        return json.dumps(structured, indent=2)
