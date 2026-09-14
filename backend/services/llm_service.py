"""
LLM Provider Abstraction Layer.
Supports OpenAI / Gemini when API keys are configured, and provides
a fallback local semantic reasoning engine so the system functions 100% out of the box without paid APIs.
"""
import os
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

from backend.config import settings

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """Abstract interface for LLM-as-a-Judge and Generation providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if the provider is configured and reachable."""
        pass

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generates plain text response."""
        pass

    @abstractmethod
    def evaluate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Generates structured JSON response."""
        pass


class OpenAILLMClient(BaseLLMClient):
    """OpenAI API integration for LLM-as-a-Judge."""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except Exception as e:
                logger.warning("Failed to initialize OpenAI client: %s", str(e))

    def is_available(self) -> bool:
        return self._client is not None and bool(self.api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.is_available():
            raise RuntimeError("OpenAI client is not configured.")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            err_str = str(e).lower()
            if "insufficient_quota" in err_str or "credit_balance_exhausted" in err_str or "401" in err_str or "429" in err_str:
                logger.warning("Disabling OpenAI client due to API limits: %s", str(e))
                self._client = None
            raise

    def evaluate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None
        messages = []
        sys = (system_prompt or "") + "\nRespond with valid JSON only."
        messages.append({"role": "system", "content": sys})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0
            )
            raw = response.choices[0].message.content
            return json.loads(raw)
        except Exception as e:
            err_str = str(e).lower()
            if "insufficient_quota" in err_str or "credit_balance_exhausted" in err_str or "401" in err_str or "429" in err_str:
                logger.warning("Disabling OpenAI client due to API credit/quota limits (%s). Gracefully falling back to local semantic engine.", str(e))
                self._client = None
            else:
                logger.error("OpenAI JSON evaluation failed: %s", str(e))
            return None


class GeminiLLMClient(BaseLLMClient):
    """Google Gemini API integration."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.is_available():
            raise RuntimeError("Gemini client is not configured.")
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        text_content = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload = {
            "contents": [{"parts": [{"text": text_content}]}],
            "generationConfig": {"temperature": 0.1}
        }
        resp = httpx.post(url, json=payload, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def evaluate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None
        text = self.generate(prompt, (system_prompt or "") + "\nOutput strictly valid JSON.")
        try:
            # Clean markdown codeblocks if returned
            cleaned = re.sub(r'```json\s*|\s*```', '', text).strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.error("Failed to parse Gemini JSON: %s", str(e))
            return None


class LLMService:
    """Manages active LLM provider with graceful fallback."""

    _instance = None

    def __init__(self):
        self.openai_client = OpenAILLMClient()
        self.gemini_client = GeminiLLMClient()

    @classmethod
    def get_instance(cls) -> "LLMService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_active_client(self) -> Optional[BaseLLMClient]:
        if self.openai_client.is_available():
            return self.openai_client
        if self.gemini_client.is_available():
            return self.gemini_client
        return None

    def has_active_llm(self) -> bool:
        return self.get_active_client() is not None


def get_llm_service() -> LLMService:
    return LLMService.get_instance()
