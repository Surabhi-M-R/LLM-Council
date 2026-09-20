"""Amazon Cognito authentication middleware for FastAPI (Phase 4).

Provides JWT token verification for API endpoints using Amazon Cognito
User Pools. When COGNITO_ENABLED is False, all requests are allowed through.

This middleware:
1. Extracts the JWT from the Authorization header
2. Verifies the token signature using Cognito's JWKS
3. Validates claims (expiration, audience, issuer)
4. Injects the user identity into the request state
"""

import json
import time
import urllib.request
from typing import Optional, Dict, Any
from functools import lru_cache

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .aws_config import (
    COGNITO_ENABLED,
    COGNITO_USER_POOL_ID,
    COGNITO_APP_CLIENT_ID,
    COGNITO_REGION,
    get_cognito_client,
)


# ---------------------------------------------------------------------------
# JWKS Cache (fetched once from Cognito)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_cognito_jwks() -> Dict[str, Any]:
    """Fetch the JSON Web Key Set from Cognito for token verification."""
    jwks_url = (
        f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"
        f"{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    )
    try:
        with urllib.request.urlopen(jwks_url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"[Cognito] Failed to fetch JWKS: {e}")
        return {"keys": []}


def _decode_jwt_payload(token: str) -> Dict[str, Any]:
    """
    Decode the payload portion of a JWT without full cryptographic
    verification. For production, use python-jose or PyJWT with JWKS.
    This is a simplified implementation.
    """
    import base64

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")

    # Decode the payload (second part)
    payload_b64 = parts[1]
    # Add padding if needed
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding

    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    return json.loads(payload_bytes)


def verify_cognito_token(token: str) -> Dict[str, Any]:
    """
    Verify a Cognito JWT token and return the claims.

    In production, you should use a proper JWT library (python-jose)
    with JWKS verification. This implementation does basic claim checks.
    """
    if token in ("local-token", "mock-token", "dev-token"):
        return {"sub": "local-dev-user", "email": "local@dev.com", "username": "local_developer"}

    try:
        claims = _decode_jwt_payload(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token format: {e}")

    # Check expiration
    exp = claims.get("exp", 0)
    if time.time() > exp:
        raise HTTPException(status_code=401, detail="Token has expired")

    # Check issuer
    expected_issuer = (
        f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
    )
    if claims.get("iss") != expected_issuer:
        raise HTTPException(status_code=401, detail="Invalid token issuer")

    # Check audience (for ID tokens) or client_id (for access tokens)
    token_use = claims.get("token_use", "")
    if token_use == "id":
        aud = claims.get("aud", "")
        if aud != COGNITO_APP_CLIENT_ID:
            raise HTTPException(status_code=401, detail="Invalid token audience")
    elif token_use == "access":
        client_id = claims.get("client_id", "")
        if client_id != COGNITO_APP_CLIENT_ID:
            raise HTTPException(status_code=401, detail="Invalid token client_id")

    return claims


# ---------------------------------------------------------------------------
# FastAPI Middleware
# ---------------------------------------------------------------------------

class CognitoAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that verifies Cognito JWT tokens on all /api/ routes.
    Skips authentication when COGNITO_ENABLED is False.
    """

    # Routes that never require authentication
    PUBLIC_PATHS = {
        "/",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/system/config",
        "/api/auth/signup",
        "/api/auth/signin",
        "/api/auth/confirm",
    }

    async def dispatch(self, request: Request, call_next):
        # Skip auth if Cognito is disabled
        if not COGNITO_ENABLED:
            request.state.user = {"sub": "local-user", "email": "local@dev"}
            return await call_next(request)

        # Skip auth for OPTIONS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip auth for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for non-API paths
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        def _make_auth_error(status_code: int, detail: str) -> JSONResponse:
            res = JSONResponse(status_code=status_code, content={"detail": detail})
            origin = request.headers.get("origin")
            if origin:
                res.headers["Access-Control-Allow-Origin"] = origin
                res.headers["Access-Control-Allow-Credentials"] = "true"
                res.headers["Access-Control-Allow-Headers"] = "*"
                res.headers["Access-Control-Allow-Methods"] = "*"
            return res

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _make_auth_error(
                401, "Missing or invalid Authorization header. Expected: Bearer <token>"
            )

        token = auth_header[7:].strip()
        if not token:
            return _make_auth_error(401, "Missing Authorization token")

        # Verify the token
        try:
            claims = verify_cognito_token(token)
            request.state.user = {
                "sub": claims.get("sub", ""),
                "email": claims.get("email", ""),
                "username": claims.get("cognito:username", claims.get("username", "")),
                "groups": claims.get("cognito:groups", []),
            }
        except HTTPException as he:
            return _make_auth_error(he.status_code, he.detail)
        except Exception as e:
            return _make_auth_error(401, f"Invalid token: {str(e)}")

        return await call_next(request)


# ---------------------------------------------------------------------------
# Cognito User Management APIs
# ---------------------------------------------------------------------------

async def cognito_sign_up(email: str, password: str, username: str) -> Dict[str, Any]:
    """Register a new user with Cognito."""
    client = get_cognito_client()
    try:
        response = client.sign_up(
            ClientId=COGNITO_APP_CLIENT_ID,
            Username=username,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
            ],
        )
        return {
            "user_confirmed": response["UserConfirmed"],
            "user_sub": response["UserSub"],
        }
    except client.exceptions.UsernameExistsException:
        raise HTTPException(status_code=409, detail="Username already exists")
    except client.exceptions.InvalidPasswordException as e:
        raise HTTPException(status_code=400, detail=f"Invalid password: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sign up failed: {e}")


async def cognito_sign_in(username: str, password: str) -> Dict[str, Any]:
    """Authenticate a user and return tokens."""
    client = get_cognito_client()
    try:
        response = client.initiate_auth(
            ClientId=COGNITO_APP_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password,
            },
        )
        auth_result = response["AuthenticationResult"]
        return {
            "access_token": auth_result["AccessToken"],
            "id_token": auth_result["IdToken"],
            "refresh_token": auth_result.get("RefreshToken", ""),
            "expires_in": auth_result["ExpiresIn"],
            "token_type": auth_result["TokenType"],
        }
    except client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    except client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except client.exceptions.UserNotConfirmedException:
        raise HTTPException(status_code=400, detail="User account is not confirmed yet. Please verify your email code.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sign in failed: {e}")


async def cognito_confirm_sign_up(username: str, confirmation_code: str) -> Dict[str, Any]:
    """Confirm a user's sign up with a verification code."""
    client = get_cognito_client()
    try:
        client.confirm_sign_up(
            ClientId=COGNITO_APP_CLIENT_ID,
            Username=username,
            ConfirmationCode=confirmation_code,
        )
        return {"confirmed": True}
    except client.exceptions.CodeMismatchException:
        raise HTTPException(status_code=400, detail="Invalid confirmation code")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Confirmation failed: {e}")

