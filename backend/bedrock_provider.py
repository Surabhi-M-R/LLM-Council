"""Amazon Bedrock API client for making LLM requests (Phase 2).

This module provides the same interface as openrouter.py but talks to
Amazon Bedrock instead. It uses the Converse API which provides a unified
interface across all Bedrock-supported models.
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional
from functools import partial

from .aws_config import (
    get_bedrock_runtime_client,
    BEDROCK_COUNCIL_MODELS,
    BEDROCK_CHAIRMAN_MODEL,
    BEDROCK_MODELS,
    BEDROCK_REGION,
)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class BedrockError(RuntimeError):
    """Raised when Bedrock rejects a request."""

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

def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English."""
    return max(1, len(text) // 4)


def get_friendly_name(model_id: str) -> str:
    """Get a human-readable name for a Bedrock model ID."""
    return BEDROCK_MODELS.get(model_id, model_id)


# ---------------------------------------------------------------------------
# Core API call using Bedrock Converse API
# ---------------------------------------------------------------------------

def _invoke_bedrock_sync(
    model_id: str,
    messages: List[Dict[str, str]],
    max_tokens: int = 2048,
) -> Dict[str, Any]:
    """
    Synchronous Bedrock Converse API call.
    Runs in a thread pool via asyncio to avoid blocking the event loop.
    """
    client = get_bedrock_runtime_client()

    # Convert our message format to Bedrock Converse format
    bedrock_messages = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            bedrock_messages.append({
                "role": "user",
                "content": [{"text": msg["content"]}],
            })
        elif role == "assistant":
            bedrock_messages.append({
                "role": "assistant",
                "content": [{"text": msg["content"]}],
            })

    try:
        response = client.converse(
            modelId=model_id,
            messages=bedrock_messages,
            inferenceConfig={
                "maxTokens": max_tokens,
                "temperature": 0.7,
            },
        )

        # Extract the response text
        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])

        response_text = ""
        for block in content_blocks:
            if "text" in block:
                response_text += block["text"]

        # Extract usage metrics for CloudWatch
        usage = response.get("usage", {})

        return {
            "content": response_text,
            "usage": {
                "input_tokens": usage.get("inputTokens", 0),
                "output_tokens": usage.get("outputTokens", 0),
                "total_tokens": usage.get("inputTokens", 0) + usage.get("outputTokens", 0),
            },
            "model_id": model_id,
            "stop_reason": response.get("stopReason", ""),
        }

    except client.exceptions.ValidationException as e:
        error_msg = str(e)
        if "operation not allowed" in error_msg.lower():
            raise BedrockError(
                f"AWS Bedrock Model Access Not Enabled for model '{model_id}'. "
                f"Please open the AWS Bedrock Console, navigate to 'Model access', and enable access for this model. Details: {error_msg}",
                status_code=403,
                is_token_limit=False,
            )
        is_token = "too many" in error_msg.lower() or "input is too long" in error_msg.lower()
        raise BedrockError(error_msg, status_code=400, is_token_limit=is_token)

    except client.exceptions.ThrottlingException as e:
        raise BedrockError(
            f"Bedrock rate limit hit for {model_id}: {e}",
            status_code=429,
            is_token_limit=False,
        )

    except client.exceptions.AccessDeniedException as e:
        raise BedrockError(
            f"Access denied for model '{model_id}'. Ensure model access is enabled in the AWS Bedrock Console (Bedrock > Model access). Error: {e}",
            status_code=403,
            is_token_limit=False,
        )

    except client.exceptions.ResourceNotFoundException as e:
        raise BedrockError(
            f"Model '{model_id}' was not found or is deprecated in AWS region {BEDROCK_REGION}. Check model ID and region. Error: {e}",
            status_code=404,
            is_token_limit=False,
        )

    except Exception as e:
        error_msg = str(e)
        if "operation not allowed" in error_msg.lower():
            raise BedrockError(
                f"AWS Bedrock Model Access Not Enabled for model '{model_id}'. Please enable model access in the AWS Bedrock Console under 'Model access'. Details: {error_msg}",
                status_code=403,
                is_token_limit=False,
            )
        raise BedrockError(
            f"Bedrock request failed for {model_id}: {e}"
        ) from e


async def query_model(
    model_id: str,
    messages: List[Dict[str, str]],
    max_tokens: int = 2048,
    max_retries: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Async wrapper around the synchronous Bedrock Converse API call.
    Runs the blocking call in a thread pool executor.
    """
    loop = asyncio.get_event_loop()
    attempt = 0

    while attempt <= max_retries:
        try:
            result = await loop.run_in_executor(
                None,
                partial(_invoke_bedrock_sync, model_id, messages, max_tokens),
            )
            return result

        except BedrockError as e:
            if e.status_code == 429 and attempt < max_retries:
                print(f"[Bedrock:{model_id}] Rate limited. Waiting 3s and retrying…")
                await asyncio.sleep(3)
                attempt += 1
                continue

            if e.is_token_limit and attempt < max_retries:
                print(f"[Bedrock:{model_id}] Token limit hit. Truncating and retrying…")
                # Truncate the last user message
                messages = _truncate_messages(messages, max_tokens * 2)
                attempt += 1
                continue

            # Return error dict instead of raising (graceful degradation)
            return {
                "error": str(e),
                "status_code": e.status_code,
                "is_token_limit": e.is_token_limit,
            }

        except Exception as e:
            return {"error": f"Bedrock request failed: {e}"}

    return None


def _truncate_messages(
    messages: List[Dict[str, str]], max_chars: int
) -> List[Dict[str, str]]:
    """Truncate the last user message to fit within the budget."""
    out = []
    for msg in messages:
        if msg["role"] == "user" and msg is messages[-1]:
            content = msg["content"]
            if len(content) > max_chars:
                content = content[:max_chars - 60] + "\n\n[... truncated to fit context window ...]"
            out.append({"role": "user", "content": content})
        else:
            out.append(msg)
    return out


# ---------------------------------------------------------------------------
# Parallel queries
# ---------------------------------------------------------------------------

async def query_models_parallel(
    model_ids: List[str],
    messages: List[Dict[str, str]],
    max_tokens: int = 2048,
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple Bedrock models in parallel.

    Returns:
        Dict mapping model identifier → response dict (or error dict).
    """
    tasks = [query_model(model_id, messages, max_tokens) for model_id in model_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses: Dict[str, Optional[Dict[str, Any]]] = {}
    for model_id, result in zip(model_ids, results):
        if isinstance(result, Exception):
            responses[model_id] = {"error": f"Request failed: {result}"}
        else:
            responses[model_id] = result

    return responses
