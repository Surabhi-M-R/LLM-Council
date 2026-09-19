"""Configuration for the LLM Council."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root directory (parent of the backend/ package)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of active, valid OpenRouter model identifiers
COUNCIL_MODELS = [
    "openai/gpt-4o-mini",
    "google/gemini-2.5-flash",
    "anthropic/claude-3-haiku",
    "meta-llama/llama-3.1-8b-instruct",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "openai/gpt-4o-mini"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage (absolute path)
DATA_DIR = str(_PROJECT_ROOT / "data" / "conversations")

# -------------------------------------------------------------------
# Token / context-window management
# -------------------------------------------------------------------
# Approximate context windows (input tokens) for each model.
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "openai/gpt-4o-mini":               124_000,   # 128k context
    "google/gemini-2.5-flash":          1_000_000,  # 1M context
    "anthropic/claude-3-haiku":         190_000,    # 200k context
    "meta-llama/llama-3.1-8b-instruct": 124_000,   # 128k context
}
DEFAULT_CONTEXT_LIMIT = 30_000  # fallback for unknown models

# How many tokens to reserve for the model's response.
# Kept modest (1500 tokens) so OpenRouter credit reservation check passes on all accounts.
RESPONSE_TOKEN_RESERVE = 1_500

# Maximum characters per individual model response when building
# the Stage 2/3 prompts.  ~4 chars ≈ 1 token, so 8000 chars ≈ 2000 tokens.
MAX_RESPONSE_CHARS = 8_000

# Maximum characters for the entire Stage 2 ranking text when building
# the Stage 3 prompt.
MAX_RANKING_CHARS = 6_000

