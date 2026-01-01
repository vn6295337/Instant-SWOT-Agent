"""
Multi-provider LLM client with cascading fallback.
Adopts pattern from Enterprise-AI-Gateway for resilient LLM access.
"""

import os
import time
import requests
from typing import Optional, Tuple

class LLMClient:
    """LLM client with automatic provider fallback."""

    def __init__(self):
        """Initialize client with available providers based on API keys."""
        self.providers = []

        # Build providers list dynamically based on available API keys
        if os.getenv("GROQ_API_KEY"):
            self.providers.append({
                "name": "groq",
                "key": os.getenv("GROQ_API_KEY"),
                "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                "url": "https://api.groq.com/openai/v1/chat/completions"
            })

        if os.getenv("GEMINI_API_KEY"):
            self.providers.append({
                "name": "gemini",
                "key": os.getenv("GEMINI_API_KEY"),
                "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
            })

        if os.getenv("OPENROUTER_API_KEY"):
            self.providers.append({
                "name": "openrouter",
                "key": os.getenv("OPENROUTER_API_KEY"),
                "model": os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free"),
                "url": "https://openrouter.ai/api/v1/chat/completions"
            })

        if not self.providers:
            raise ValueError("No LLM API keys configured. Set at least one of: GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY")

    def query(self, prompt: str, temperature: float = 0, max_tokens: int = 2048) -> Tuple[Optional[str], Optional[str], Optional[str], list]:
        """
        Query LLM with cascading fallback across providers.

        Returns:
            Tuple of (response_content, provider_used, error_message, providers_failed)
            providers_failed is a list of dicts: [{"name": "gemini", "error": "..."}]
        """
        errors = []
        providers_failed = []

        for provider in self.providers:
            print(f"Attempting LLM call with {provider['name']}...")
            start_time = time.perf_counter()

            try:
                content, error = self._call_provider(
                    provider=provider,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                latency_ms = int((time.perf_counter() - start_time) * 1000)

                if content:
                    print(f"Success with {provider['name']} ({latency_ms}ms)")
                    # Return provider:model format for detailed logging
                    provider_info = f"{provider['name']}:{provider['model']}"
                    return content, provider_info, None, providers_failed
                else:
                    errors.append(f"{provider['name']}: {error}")
                    providers_failed.append({"name": provider['name'], "error": error})
                    print(f"Provider {provider['name']} failed: {error}")

            except Exception as e:
                errors.append(f"{provider['name']}: {str(e)}")
                providers_failed.append({"name": provider['name'], "error": str(e)})
                print(f"Provider {provider['name']} exception: {e}")

        return None, None, f"All LLM providers failed: {'; '.join(errors)}", providers_failed

    def _call_provider(self, provider: dict, prompt: str, temperature: float, max_tokens: int) -> Tuple[Optional[str], Optional[str]]:
        """Call a specific LLM provider."""
        headers = {"Content-Type": "application/json"}

        if provider["name"] == "groq":
            headers["Authorization"] = f"Bearer {provider['key']}"
            payload = {
                "model": provider["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            response = requests.post(provider["url"], headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data and "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"], None
            return None, "No content in Groq response"

        elif provider["name"] == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{provider['model']}:generateContent?key={provider['key']}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                }
            }
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data and "candidates" in data and data["candidates"]:
                first_candidate = data["candidates"][0]
                if "content" in first_candidate and "parts" in first_candidate["content"]:
                    for part in first_candidate["content"]["parts"]:
                        if "text" in part:
                            return part["text"], None
            return None, "No text content in Gemini response"

        elif provider["name"] == "openrouter":
            headers["Authorization"] = f"Bearer {provider['key']}"
            headers["HTTP-Referer"] = "https://huggingface.co/spaces"
            headers["X-Title"] = "Instant SWOT Agent"
            payload = {
                "model": provider["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            response = requests.post(provider["url"], headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data and "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"], None
            return None, "No content in OpenRouter response"

        return None, f"Unknown provider: {provider['name']}"


# Singleton instance
_client = None

def get_llm_client() -> LLMClient:
    """Get or create the singleton LLM client instance."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
