"""Hybrid model router for LLM Council.

Routes queries to either OpenRouter or Bedrock based on the model identifier prefix.
In hybrid mode, model IDs are prefixed with "openrouter:" or "bedrock:".
In single-provider modes, the router delegates to the appropriate provider directly.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple

from .config import LLM_PROVIDER, get_council_models, get_chairman_model
from .cloudwatch_metrics import (
    record_model_latency,
    record_token_usage,
    record_error,
    MetricsTimer,
)


async def query_model(
    model_id: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    max_retries: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Route a model query to the correct provider.

    Args:
        model_id: Model identifier. In hybrid mode, prefixed with "openrouter:" or "bedrock:".
        messages: Chat messages in standard format.
        timeout: Request timeout in seconds (used by OpenRouter).
        max_retries: Number of retries on failure.

    Returns:
        Response dict with 'content' key, or error dict, or None.
    """
    timer = MetricsTimer().start()

    # Determine provider and clean model ID
    provider, clean_model_id = _parse_model_id(model_id)

    try:
        if provider == "bedrock":
            from .bedrock_provider import query_model as bedrock_query
            result = await bedrock_query(clean_model_id, messages, max_retries=max_retries)
        else:
            from .openrouter import query_model as openrouter_query
            result = await openrouter_query(clean_model_id, messages, timeout=timeout, max_retries=max_retries)

        timer.stop()

        # Record metrics
        if result and not isinstance(result, dict):
            pass
        elif result and "error" not in result:
            await record_model_latency(clean_model_id, provider, timer.elapsed_ms)
            # Record token usage if available (Bedrock provides this)
            usage = result.get("usage", {})
            if usage:
                await record_token_usage(
                    clean_model_id,
                    provider,
                    usage.get("input_tokens", 0),
                    usage.get("output_tokens", 0),
                )
        elif result and "error" in result:
            await record_error(clean_model_id, provider, "api_error")

        return result

    except Exception as e:
        timer.stop()
        await record_error(clean_model_id, provider, type(e).__name__)
        return {"error": str(e)}


async def query_models_parallel(
    model_ids: List[str],
    messages: List[Dict[str, str]],
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel, routing each to the correct provider.

    Returns:
        Dict mapping original model_id → response dict (or error dict).
    """
    tasks = [query_model(model_id, messages) for model_id in model_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses: Dict[str, Optional[Dict[str, Any]]] = {}
    for model_id, result in zip(model_ids, results):
        if isinstance(result, Exception):
            responses[model_id] = {"error": f"Request failed: {result}"}
        else:
            responses[model_id] = result

    return responses


def _parse_model_id(model_id: str) -> Tuple[str, str]:
    """
    Parse a model ID to determine the provider and clean model name.

    In hybrid mode: "bedrock:anthropic.claude-3-5-sonnet..." → ("bedrock", "anthropic.claude-3-5-sonnet...")
    In single mode: "openai/gpt-4o-mini" → ("openrouter", "openai/gpt-4o-mini")
    """
    if model_id.startswith("bedrock:"):
        return "bedrock", model_id[8:]
    elif model_id.startswith("openrouter:"):
        return "openrouter", model_id[11:]
    else:
        # No prefix – use the default provider
        if LLM_PROVIDER == "bedrock":
            return "bedrock", model_id
        else:
            return "openrouter", model_id


def get_display_name(model_id: str) -> str:
    """Get a human-readable display name for a model ID."""
    _, clean_id = _parse_model_id(model_id)

    # For OpenRouter models: "openai/gpt-4o-mini" → "gpt-4o-mini"
    if "/" in clean_id:
        return clean_id.split("/")[1]

    # For Bedrock models: use friendly name mapping
    from .aws_config import BEDROCK_MODELS
    return BEDROCK_MODELS.get(clean_id, clean_id.split(".")[-1] if "." in clean_id else clean_id)
