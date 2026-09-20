"""3-stage LLM Council orchestration.

Updated to use the hybrid model router (OpenRouter + Bedrock) and
dynamic model configuration from config.py.
"""

from typing import List, Dict, Any, Tuple
from .model_router import query_model, query_models_parallel, get_display_name
from .config import get_council_models, get_chairman_model, MAX_RESPONSE_CHARS, MAX_RANKING_CHARS
from .cloudwatch_metrics import record_council_deliberation, MetricsTimer

# Keep direct imports for token management helpers
from .openrouter import truncate_to_token_budget, estimate_tokens, get_max_input_tokens


# ---------------------------------------------------------------------------
# Helpers – prompt-size management
# ---------------------------------------------------------------------------

def _truncate_response(text: str, max_chars: int = MAX_RESPONSE_CHARS) -> str:
    """Trim a single model response so it doesn't blow up later prompts."""
    if not text or len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 45)] + "\n\n[... response truncated for brevity ...]"


def _truncate_ranking(text: str, max_chars: int = MAX_RANKING_CHARS) -> str:
    """Trim a single ranking evaluation."""
    if not text or len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 45)] + "\n\n[... ranking truncated for brevity ...]"


def _build_and_fit_prompt(prompt_template: str, model: str) -> str:
    """Ensure *prompt_template* fits within the model's context budget.
    If it's too long, truncate the end (which is usually the data section)."""
    try:
        max_input = get_max_input_tokens(model)
        est = estimate_tokens(prompt_template)
        if est <= max_input:
            return prompt_template
        return truncate_to_token_budget(prompt_template, max_input)
    except Exception:
        # If we can't determine context limits (e.g., for Bedrock models),
        # just return the prompt as-is
        return prompt_template


# ---------------------------------------------------------------------------
MODEL_BEDROCK_DISPLAY = {
    'openai/gpt-4o-mini': 'us.amazon.nova-pro-v1:0',
    'google/gemini-2.5-flash': 'us.amazon.nova-lite-v1:0',
    'anthropic/claude-3-haiku': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
    'meta-llama/llama-3.1-8b-instruct': 'us.meta.llama3-3-70b-instruct-v1:0',
}

def _to_bedrock_model_name(model_id: str) -> str:
    return MODEL_BEDROCK_DISPLAY.get(model_id, model_id)


# ---------------------------------------------------------------------------
# Stage 1 – collect individual responses
# ---------------------------------------------------------------------------

async def stage1_collect_responses(user_query: str) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    council_models = get_council_models()
    messages = [{"role": "user", "content": user_query}]

    # Query all models in parallel via the hybrid router
    responses = await query_models_parallel(council_models, messages)

    stage1_results = []
    for model, response in responses.items():
        display_model = _to_bedrock_model_name(model)
        if response is not None:
            if isinstance(response, dict) and response.get('error'):
                stage1_results.append({
                    "model": display_model,
                    "response": "",
                    "error": response.get('error'),
                    "status_code": response.get('status_code')
                })
            else:
                stage1_results.append({
                    "model": display_model,
                    "response": response.get('content', '')
                })

    return stage1_results


# ---------------------------------------------------------------------------
# Stage 2 – peer rankings
# ---------------------------------------------------------------------------

async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Individual Stage-1 responses are truncated before being embedded in the
    ranking prompt so that even models with small context windows can evaluate
    them without triggering a token-limit error.
    """
    council_models = get_council_models()

    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt – truncate each response to stay within budget
    responses_text = "\n\n".join([
        f"Response {label}:\n{_truncate_response(result['response'])}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(council_models, messages)

    stage2_results = []
    for model, response in responses.items():
        display_model = _to_bedrock_model_name(model)
        if response is not None:
            if isinstance(response, dict) and response.get('error'):
                stage2_results.append({
                    "model": display_model,
                    "ranking": "",
                    "parsed_ranking": [],
                    "error": response.get('error'),
                    "status_code": response.get('status_code')
                })
                continue

            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": display_model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


# ---------------------------------------------------------------------------
# Stage 3 – chairman synthesis
# ---------------------------------------------------------------------------

async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Both Stage-1 responses and Stage-2 rankings are truncated before
    building the chairman prompt to avoid blowing the context window.
    """
    chairman_model = get_chairman_model()
    display_chairman = _to_bedrock_model_name(chairman_model)

    # Build comprehensive context for chairman – with truncation
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {_truncate_response(result['response'])}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {_truncate_ranking(result['ranking'])}"
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    # Final safety net: ensure the prompt fits the chairman model
    chairman_prompt = _build_and_fit_prompt(chairman_prompt, chairman_model)

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model via the hybrid router
    try:
        response = await query_model(chairman_model, messages)
    except Exception as e:
        return {
            "model": display_chairman,
            "response": "Error: Unable to generate final synthesis.",
            "error": str(e)
        }

    if response is None:
        return {
            "model": display_chairman,
            "response": "Error: Unable to generate final synthesis.",
            "error": "The chairman model request failed. Check your API key or quota."
        }

    if isinstance(response, dict) and response.get('error'):
        return {
            "model": display_chairman,
            "response": "Error: Unable to generate final synthesis.",
            "error": response.get('error')
        }

    return {
        "model": display_chairman,
        "response": response.get('content', '')
    }


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(
                r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


# ---------------------------------------------------------------------------
# Title generation
# ---------------------------------------------------------------------------

async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    # Truncate very long queries for title generation (no point sending 10k chars)
    truncated_query = user_query[:2000] if len(user_query) > 2000 else user_query

    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {truncated_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    try:
        # Use the first council model for title generation (fast and cheap)
        council_models = get_council_models()
        title_model = council_models[0] if council_models else get_chairman_model()
        response = await query_model(title_model, messages, timeout=30.0)
    except Exception:
        return "New Conversation"

    if response is None:
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


# ---------------------------------------------------------------------------
# Full council runner
# ---------------------------------------------------------------------------

async def run_full_council(user_query: str) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    total_timer = MetricsTimer().start()

    # Stage 1: Collect individual responses
    s1_timer = MetricsTimer().start()
    stage1_results = await stage1_collect_responses(user_query)
    s1_timer.stop()

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Stage 2: Collect rankings
    s2_timer = MetricsTimer().start()
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)
    s2_timer.stop()

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(
        stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    s3_timer = MetricsTimer().start()
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results
    )
    s3_timer.stop()

    total_timer.stop()

    # Publish timing metrics to CloudWatch
    await record_council_deliberation(
        total_time_ms=total_timer.elapsed_ms,
        stage1_time_ms=s1_timer.elapsed_ms,
        stage2_time_ms=s2_timer.elapsed_ms,
        stage3_time_ms=s3_timer.elapsed_ms,
        num_models=len(get_council_models()),
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "provider": get_council_models()[0].split(":")[0] if ":" in get_council_models()[0] else "openrouter",
        "timing": {
            "total_ms": round(total_timer.elapsed_ms, 1),
            "stage1_ms": round(s1_timer.elapsed_ms, 1),
            "stage2_ms": round(s2_timer.elapsed_ms, 1),
            "stage3_ms": round(s3_timer.elapsed_ms, 1),
        }
    }

    return stage1_results, stage2_results, stage3_result, metadata
