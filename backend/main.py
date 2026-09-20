"""FastAPI backend for LLM Council — AWS-Integrated Edition.

Integrates:
  - Phase 1: DynamoDB storage (configurable via STORAGE_BACKEND env var)
  - Phase 2: Amazon Bedrock models (configurable via LLM_PROVIDER env var)
  - Phase 3: Deployment-ready CORS & health checks
  - Phase 4: Cognito auth middleware, CloudWatch metrics, Auth endpoints
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
import time
import os

from .config import STORAGE_BACKEND, LLM_PROVIDER, get_council_models, get_chairman_model
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
)
from .cognito_auth import CognitoAuthMiddleware
from .cloudwatch_metrics import record_api_request
from .aws_config import (
    COGNITO_ENABLED,
    CLOUDWATCH_ENABLED,
    BEDROCK_ENABLED,
    AWS_REGION,
)


# ---------------------------------------------------------------------------
# Storage Backend Selection
# ---------------------------------------------------------------------------

def _get_storage():
    """
    Return the appropriate storage module based on STORAGE_BACKEND config.
    """
    if STORAGE_BACKEND == "dynamodb":
        from . import dynamodb_storage
        return dynamodb_storage
    else:
        from . import storage
        return storage


# ---------------------------------------------------------------------------
# FastAPI App Setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LLM Council API — AWS Edition",
    description="Multi-LLM deliberation platform powered by AWS Bedrock, DynamoDB, Cognito & CloudWatch",
    version="2.0.0",
)

# Enable CORS for local + deployed frontends
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

# If deployed, add the Amplify / CloudFront domain
amplify_domain = os.getenv("AMPLIFY_DOMAIN", "")
if amplify_domain:
    allowed_origins.append(f"https://{amplify_domain}")

cloudfront_domain = os.getenv("CLOUDFRONT_DOMAIN", "")
if cloudfront_domain:
    allowed_origins.append(f"https://{cloudfront_domain}")

# Cognito Authentication Middleware (Phase 4) - inner layer
app.add_middleware(CognitoAuthMiddleware)

# Enable CORS for local + deployed frontends - outer layer (added last so it executes outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


class AuthSignUpRequest(BaseModel):
    """Sign up request."""
    email: str
    username: str
    password: str


class AuthSignInRequest(BaseModel):
    """Sign in request."""
    username: str
    password: str


class AuthConfirmRequest(BaseModel):
    """Sign up confirmation request."""
    username: str
    confirmation_code: str


# ---------------------------------------------------------------------------
# Health & System Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "LLM Council API — AWS Edition",
        "version": "2.0.0",
    }


@app.get("/health")
async def health():
    """Detailed health check for deployment monitoring."""
    return {
        "status": "healthy",
        "provider": LLM_PROVIDER,
        "storage": STORAGE_BACKEND,
        "aws_region": AWS_REGION,
        "cognito_enabled": COGNITO_ENABLED,
        "cloudwatch_enabled": CLOUDWATCH_ENABLED,
        "bedrock_enabled": BEDROCK_ENABLED,
        "council_models": get_council_models(),
        "chairman_model": get_chairman_model(),
    }


@app.get("/api/system/config")
async def get_system_config():
    """Return the current system configuration for the frontend dashboard."""
    from .council import _to_bedrock_model_name
    return {
        "provider": "bedrock",
        "storage_backend": STORAGE_BACKEND,
        "aws_region": AWS_REGION,
        "council_models": [_to_bedrock_model_name(m) for m in get_council_models()],
        "chairman_model": _to_bedrock_model_name(get_chairman_model()),
        "cognito_enabled": COGNITO_ENABLED,
        "cloudwatch_enabled": CLOUDWATCH_ENABLED,
        "bedrock_enabled": True,
    }


# ---------------------------------------------------------------------------
# Authentication Endpoints (Phase 4 – Cognito)
# ---------------------------------------------------------------------------

@app.post("/api/auth/signup")
async def auth_signup(request: AuthSignUpRequest):
    """Register a new user via Cognito."""
    if not COGNITO_ENABLED:
        raise HTTPException(status_code=501, detail="Authentication is not enabled. Set COGNITO_ENABLED=true.")
    from .cognito_auth import cognito_sign_up
    return await cognito_sign_up(request.email, request.password, request.username)


@app.post("/api/auth/signin")
async def auth_signin(request: AuthSignInRequest):
    """Sign in and receive JWT tokens."""
    if not COGNITO_ENABLED:
        raise HTTPException(status_code=501, detail="Authentication is not enabled. Set COGNITO_ENABLED=true.")
    from .cognito_auth import cognito_sign_in
    return await cognito_sign_in(request.username, request.password)


@app.post("/api/auth/confirm")
async def auth_confirm(request: AuthConfirmRequest):
    """Confirm sign up with verification code."""
    if not COGNITO_ENABLED:
        raise HTTPException(status_code=501, detail="Authentication is not enabled. Set COGNITO_ENABLED=true.")
    from .cognito_auth import cognito_confirm_sign_up
    return await cognito_confirm_sign_up(request.username, request.confirmation_code)


@app.get("/api/auth/me")
async def auth_me(request: Request):
    """Get the current authenticated user's info."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ---------------------------------------------------------------------------
# Conversation Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    store = _get_storage()
    return store.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    store = _get_storage()
    conversation_id = str(uuid.uuid4())
    conversation = store.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    store = _get_storage()
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    store = _get_storage()
    if hasattr(store, "delete_conversation"):
        store.delete_conversation(conversation_id)
        return {"status": "deleted", "id": conversation_id}
    raise HTTPException(status_code=501, detail="Delete not supported by current storage backend")


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    start_time = time.perf_counter()
    store = _get_storage()

    # Check if conversation exists
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    store.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        store.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content
    )

    # Add assistant message with all stages
    store.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Record API metrics
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    await record_api_request("/api/conversations/message", "POST", 200, elapsed_ms)

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    store = _get_storage()

    # Check if conversation exists
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            store.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                store.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            store.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
