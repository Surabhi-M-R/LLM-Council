"""OpenRouter API client for making LLM requests."""

import asyncio
import httpx
from typing import List, Dict, Any, Optional
from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_API_URL,
    MODEL_CONTEXT_LIMITS,
    DEFAULT_CONTEXT_LIMIT,
    RESPONSE_TOKEN_RESERVE,
)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class OpenRouterError(RuntimeError):
    """Raised when OpenRouter rejects a request."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        is_token_limit: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.is_token_limit = is_token_limit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_TOKEN_LIMIT_KEYWORDS = [
    "context length",
    "context_length",
    "token limit",
    "token_limit",
    "max_tokens",
    "maximum context",
    "too many tokens",
    "reduce the length",
    "input too long",
    "prompt is too long",
    "exceeded",               # "credits exceeded" is handled separately
    "context window",
]


def _is_token_limit_error(message: str) -> bool:
    """Heuristically detect whether an API error is a token/context-limit error."""
    msg_lower = message.lower()
    # Exclude pure quota / billing errors (402)
    if "credit" in msg_lower or "quota" in msg_lower or "billing" in msg_lower:
        return False
    return any(kw in msg_lower for kw in _TOKEN_LIMIT_KEYWORDS)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English."""
    return max(1, len(text) // 4)


def get_max_input_tokens(model: str) -> int:
    """Return the maximum number of input tokens we allow for *model*."""
    limit = MODEL_CONTEXT_LIMITS.get(model, DEFAULT_CONTEXT_LIMIT)
    return limit - RESPONSE_TOKEN_RESERVE


def truncate_to_token_budget(text: str, max_tokens: int) -> str:
    """Truncate *text* so it fits roughly within *max_tokens*."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 60] + "\n\n[... truncated to fit context window ...]"


# ---------------------------------------------------------------------------
# Core API call
# ---------------------------------------------------------------------------
async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    max_retries: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Features added for token-limit resilience:
    • Sends ``max_tokens`` capped at RESPONSE_TOKEN_RESERVE so the model
      doesn't attempt an unbounded generation.
    • On a token-limit error (context too long), automatically truncates the
      last user message and retries once.
    • Detects 429 rate-limit and waits 2 s before a single retry.

    Returns:
        Response dict with 'content' and optional 'reasoning_details',
        or None if all retries are exhausted.
    """
    if not OPENROUTER_API_KEY:
        raise OpenRouterError(
            "OPENROUTER_API_KEY is missing. Add it to the .env file in the project root."
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    attempt = 0
    current_messages = messages  # may be truncated on retry

    while attempt <= max_retries:
        payload = {
            "model": model,
            "messages": current_messages,
            "max_tokens": RESPONSE_TOKEN_RESERVE,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload,
                )

                # ---- Handle HTTP errors ----
                if response.status_code >= 400:
                    try:
                        error_payload = response.json()
                        error_message = error_payload.get(
                            "error", {}
                        ).get("message", response.text)
                    except Exception:
                        error_message = response.text

                    is_token = _is_token_limit_error(error_message)

                    # 402 – billing / quota
                    if response.status_code == 402:
                        raise OpenRouterError(
                            f"OpenRouter quota exceeded or credits are exhausted. Details: {error_message}",
                            status_code=402,
                            is_token_limit=False,
                        )

                    # 429 – rate limit → wait & retry
                    if response.status_code == 429 and attempt < max_retries:
                        print(f"[{model}] Rate limited (429). Waiting 2 s and retrying…")
                        await asyncio.sleep(2)
                        attempt += 1
                        continue

                    # Token / context-length error → truncate & retry
                    if is_token and attempt < max_retries:
                        print(f"[{model}] Token limit hit. Truncating prompt and retrying…")
                        current_messages = _truncate_messages(current_messages, model)
                        attempt += 1
                        continue

                    raise OpenRouterError(
                        error_message,
                        status_code=response.status_code,
                        is_token_limit=is_token,
                    )

                # ---- Success path ----
                data = response.json()

                # OpenRouter sometimes wraps errors inside a 200 response
                if "error" in data:
                    err_msg = data["error"].get("message", str(data["error"]))
                    if _is_token_limit_error(err_msg) and attempt < max_retries:
                        print(f"[{model}] Token limit (in-body). Truncating and retrying…")
                        current_messages = _truncate_messages(current_messages, model)
                        attempt += 1
                        continue
                    raise OpenRouterError(err_msg, is_token_limit=_is_token_limit_error(err_msg))

                message = data["choices"][0]["message"]
                return {
                    "content": message.get("content"),
                    "reasoning_details": message.get("reasoning_details"),
                }

        except OpenRouterError:
            raise
        except httpx.TimeoutException:
            if attempt < max_retries:
                print(f"[{model}] Request timed out. Retrying…")
                attempt += 1
                continue
            raise OpenRouterError(
                f"Request to {model} timed out after {timeout}s",
                is_token_limit=False,
            )
        except Exception as e:
            print(f"Error querying model {model}: {e}")
            raise OpenRouterError(
                f"OpenRouter request failed for {model}: {e}"
            ) from e

    # All retries exhausted  (shouldn't normally reach here)
    return None


def _truncate_messages(
    messages: List[Dict[str, str]], model: str
) -> List[Dict[str, str]]:
    """Return a copy of *messages* with the last user message trimmed to ~60 %
    of the model's context budget."""
    budget = int(get_max_input_tokens(model) * 0.6)
    out = []
    for msg in messages:
        if msg["role"] == "user" and msg is messages[-1]:
            out.append({
                "role": "user",
                "content": truncate_to_token_budget(msg["content"], budget),
            })
        else:
            out.append(msg)
    return out


# ---------------------------------------------------------------------------
# Parallel queries
# ---------------------------------------------------------------------------
async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Returns:
        Dict mapping model identifier → response dict (or error dict).
    """
    tasks = [query_model(model, messages) for model in models]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses: Dict[str, Optional[Dict[str, Any]]] = {}
    for model, result in zip(models, results):
        if isinstance(result, OpenRouterError):
            responses[model] = {
                "error": str(result),
                "status_code": result.status_code,
                "is_token_limit": result.is_token_limit,
            }
        elif isinstance(result, Exception):
            responses[model] = {"error": f"Request failed: {result}"}
        else:
            responses[model] = result

    return responses
