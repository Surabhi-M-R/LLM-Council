"""Configuration for the LLM Council."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root directory (parent of the backend/ package)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Provider selection: "openrouter", "bedrock", or "hybrid"
# - "openrouter": Use OpenRouter API only (original behavior)
# - "bedrock":    Use Amazon Bedrock only
# - "hybrid":     Use BOTH providers, combining models from each
# ---------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").lower()

# ---------------------------------------------------------------------------
# Storage backend: "json" or "dynamodb"
# - "json":     Local JSON file storage (original behavior)
# - "dynamodb": Amazon DynamoDB cloud storage
# ---------------------------------------------------------------------------
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "json").lower()

# ---------------------------------------------------------------------------
# OpenRouter Configuration
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of active, valid OpenRouter model identifiers
OPENROUTER_COUNCIL_MODELS = [
    "openai/gpt-4o-mini",
    "google/gemini-2.5-flash",
    "anthropic/claude-3-haiku",
    "meta-llama/llama-3.1-8b-instruct",
]

# Chairman model - synthesizes final response
OPENROUTER_CHAIRMAN_MODEL = "openai/gpt-4o-mini"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# ---------------------------------------------------------------------------
# Dynamic model list based on provider
# ---------------------------------------------------------------------------
def get_council_models():
    """Return the list of council model IDs based on the active provider."""
    if LLM_PROVIDER == "bedrock":
        from .aws_config import BEDROCK_COUNCIL_MODELS
        return BEDROCK_COUNCIL_MODELS
    elif LLM_PROVIDER == "hybrid":
        from .aws_config import BEDROCK_COUNCIL_MODELS
        # Prefix bedrock models with "bedrock:" for the hybrid router
        bedrock = [f"bedrock:{m}" for m in BEDROCK_COUNCIL_MODELS]
        openrouter = [f"openrouter:{m}" for m in OPENROUTER_COUNCIL_MODELS]
        return openrouter + bedrock
    else:
        return OPENROUTER_COUNCIL_MODELS


def get_chairman_model():
    """Return the chairman model ID based on the active provider."""
    if LLM_PROVIDER == "bedrock":
        from .aws_config import BEDROCK_CHAIRMAN_MODEL
        return BEDROCK_CHAIRMAN_MODEL
    elif LLM_PROVIDER == "hybrid":
        from .aws_config import BEDROCK_CHAIRMAN_MODEL
        return f"bedrock:{BEDROCK_CHAIRMAN_MODEL}"
    else:
        return OPENROUTER_CHAIRMAN_MODEL


# Keep legacy names for backward compatibility
COUNCIL_MODELS = OPENROUTER_COUNCIL_MODELS
CHAIRMAN_MODEL = OPENROUTER_CHAIRMAN_MODEL

# Data directory for conversation storage (absolute path) – used by JSON backend
DATA_DIR = str(_PROJECT_ROOT / "data" / "conversations")

# -------------------------------------------------------------------
# Token / context-window management
# -------------------------------------------------------------------
# Approximate context windows (input tokens) for each model.
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    # OpenRouter models
    "openai/gpt-4o-mini":               124_000,
    "google/gemini-2.5-flash":          1_000_000,
    "anthropic/claude-3-haiku":         190_000,
    "meta-llama/llama-3.1-8b-instruct": 124_000,
    # Bedrock models
    "us.amazon.nova-pro-v1:0":                   300_000,
    "us.amazon.nova-lite-v1:0":                  300_000,
    "us.amazon.nova-micro-v1:0":                 128_000,
    "us.meta.llama3-3-70b-instruct-v1:0":        128_000,
    "us.meta.llama3-1-8b-instruct-v1:0":         128_000,
    "us.anthropic.claude-3-5-sonnet-20241022-v2:0": 200_000,
    "us.anthropic.claude-3-haiku-20240307-v1:0":    200_000,
    "anthropic.claude-3-haiku-20240307-v1:0":    200_000,
}
DEFAULT_CONTEXT_LIMIT = 30_000  # fallback for unknown models

# How many tokens to reserve for the model's response.
RESPONSE_TOKEN_RESERVE = 1_500

# Maximum characters per individual model response when building
# the Stage 2/3 prompts.  ~4 chars ≈ 1 token, so 8000 chars ≈ 2000 tokens.
MAX_RESPONSE_CHARS = 8_000

# Maximum characters for the entire Stage 2 ranking text when building
# the Stage 3 prompt.
MAX_RANKING_CHARS = 6_000
