"""
Multi-provider LLM client with cascading fallback.
Adopts pattern from Enterprise-AI-Gateway for resilient LLM access.
"""

import os
import time
import requests
from typing import Optional, Tuple

# Retry configuration - rotate through providers instead of consecutive retries
MAX_ROUNDS = 3  # Number of times to cycle through all providers
PROVIDER_DELAY = 10  # seconds between provider attempts


class LLMClient:
    """LLM client with automatic provider fallback."""

    def __init__(self, override_keys: dict = None):
        """Initialize client with available providers based on API keys.

        Args:
            override_keys: Optional dict with user-provided API keys.
                          Keys: "groq", "gemini", "openrouter"
        """
        self.providers = []
        override_keys = override_keys or {}

        # Build providers list - use override keys if provided, else env vars
        groq_key = override_keys.get("groq") or os.getenv("GROQ_API_KEY")
        gemini_key = override_keys.get("gemini") or os.getenv("GEMINI_API_KEY")
        openrouter_key = override_keys.get("openrouter") or os.getenv("OPENROUTER_API_KEY")

        if groq_key:
            self.providers.append({
                "name": "groq",
                "key": groq_key,
                "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
                "url": "https://api.groq.com/openai/v1/chat/completions"
            })

        if gemini_key:
            self.providers.append({
                "name": "gemini",
                "key": gemini_key,
                "model": os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
            })

        if openrouter_key:
            self.providers.append({
                "name": "openrouter",
                "key": openrouter_key,
                "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free"),
                "url": "https://openrouter.ai/api/v1/chat/completions"
            })

        if not self.providers:
            raise ValueError("No LLM API keys configured. Set at least one of: GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY")

    def query(self, prompt: str, temperature: float = 0, max_tokens: int = 2048,
              json_mode: bool = False) -> Tuple[Optional[str], Optional[str], Optional[str], list]:
        """
        Query LLM with rotating fallback across providers.

        json_mode=True forces valid-JSON output (response_format json_object on
        Groq/OpenRouter, responseMimeType on Gemini). The prompt must still
        mention JSON explicitly - providers require it.

        Instead of retrying same provider consecutively, rotates:
        Groq → Gemini → OpenRouter → Groq → Gemini → OpenRouter → ...

        Returns:
            Tuple of (response_content, provider_used, error_message, providers_failed)
            providers_failed is a list of dicts: [{"name": "gemini", "error": "..."}]
        """
        errors = []
        providers_failed = []
        is_first_attempt = True

        # Rotate through providers for MAX_ROUNDS cycles
        for round_num in range(MAX_ROUNDS):
            for provider in self.providers:
                # Add delay between attempts (skip first attempt)
                if not is_first_attempt:
                    print(f"Waiting {PROVIDER_DELAY}s before trying {provider['name']} (round {round_num + 1})...")
                    time.sleep(PROVIDER_DELAY)
                is_first_attempt = False

                print(f"Attempting LLM call with {provider['name']} (round {round_num + 1}/{MAX_ROUNDS})...")
                start_time = time.perf_counter()

                try:
                    content, error = self._call_provider(
                        provider=provider,
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode
                    )
                    latency_ms = int((time.perf_counter() - start_time) * 1000)

                    if content:
                        print(f"Success with {provider['name']} ({latency_ms}ms)")
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

        return None, None, f"All LLM providers failed after {MAX_ROUNDS} rounds: {'; '.join(errors)}", providers_failed

    def _make_request(self, url: str, headers: dict, payload: dict, provider_name: str) -> requests.Response:
        """Make HTTP request to provider (no internal retry - rotation handles retries)."""
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response

    def _call_provider(self, provider: dict, prompt: str, temperature: float,
                       max_tokens: int, json_mode: bool = False) -> Tuple[Optional[str], Optional[str]]:
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
            # gpt-oss reasoning models burn max_tokens on hidden reasoning;
            # low effort keeps the budget for actual content
            if "gpt-oss" in provider["model"]:
                payload["reasoning_effort"] = "low"
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            response = self._make_request(provider["url"], headers, payload, provider["name"])
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
            if json_mode:
                payload["generationConfig"]["responseMimeType"] = "application/json"
            response = self._make_request(url, headers, payload, provider["name"])
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
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            response = self._make_request(provider["url"], headers, payload, provider["name"])
            data = response.json()
            if data and "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"], None
            return None, "No content in OpenRouter response"

        return None, f"Unknown provider: {provider['name']}"


# Singleton instance for default (env-based) client
_client = None

def get_llm_client(override_keys: dict = None) -> LLMClient:
    """Get or create an LLM client instance.

    Args:
        override_keys: If provided, creates a new client with these keys.
                      If None/empty, returns the singleton instance.
    """
    # If user provided override keys, create a fresh client for this request
    if override_keys:
        return LLMClient(override_keys)

    # Otherwise use singleton for default env-based keys
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
