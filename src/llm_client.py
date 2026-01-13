"""
Multi-provider LLM client with cascading fallback.
Adopts pattern from Enterprise-AI-Gateway for resilient LLM access.
"""

import os
import time
import requests
from requests.exceptions import HTTPError
from typing import Optional, Tuple

# Retry configuration for rate limits
MAX_RETRIES = 3
INITIAL_BACKOFF = 5  # seconds (backoffs: 5s, 10s, 20s)


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
                "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                "url": "https://api.groq.com/openai/v1/chat/completions"
            })

        if gemini_key:
            self.providers.append({
                "name": "gemini",
                "key": gemini_key,
                "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
            })

        if openrouter_key:
            self.providers.append({
                "name": "openrouter",
                "key": openrouter_key,
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
        last_was_rate_limited = False

        for provider in self.providers:
            # Add delay before trying next provider if previous one was rate limited
            if last_was_rate_limited:
                print(f"Waiting 10s before trying {provider['name']} (rate limit cooldown)...")
                time.sleep(10)
                last_was_rate_limited = False

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
                    # Check if this was a rate limit error
                    if error and "429" in str(error):
                        last_was_rate_limited = True

            except Exception as e:
                errors.append(f"{provider['name']}: {str(e)}")
                providers_failed.append({"name": provider['name'], "error": str(e)})
                print(f"Provider {provider['name']} exception: {e}")
                # Check if this was a rate limit error
                if "429" in str(e):
                    last_was_rate_limited = True

        return None, None, f"All LLM providers failed: {'; '.join(errors)}", providers_failed

    def _request_with_retry(self, url: str, headers: dict, payload: dict, provider_name: str) -> requests.Response:
        """Make HTTP request with exponential backoff retry on 429 rate limit."""
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                return response
            except HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    last_error = e
                    if attempt < MAX_RETRIES - 1:
                        backoff = INITIAL_BACKOFF * (2 ** attempt)  # 5s, 10s, 20s
                        print(f"Rate limited by {provider_name}, retrying in {backoff}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                        time.sleep(backoff)
                        continue
                # Re-raise non-429 errors or final 429
                raise
            except Exception:
                raise

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise Exception(f"Request failed after {MAX_RETRIES} attempts")

    def _call_provider(self, provider: dict, prompt: str, temperature: float, max_tokens: int) -> Tuple[Optional[str], Optional[str]]:
        """Call a specific LLM provider with retry on rate limit."""
        headers = {"Content-Type": "application/json"}

        if provider["name"] == "groq":
            headers["Authorization"] = f"Bearer {provider['key']}"
            payload = {
                "model": provider["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            response = self._request_with_retry(provider["url"], headers, payload, provider["name"])
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
            response = self._request_with_retry(url, headers, payload, provider["name"])
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
            response = self._request_with_retry(provider["url"], headers, payload, provider["name"])
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
