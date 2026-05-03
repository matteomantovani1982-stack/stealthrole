"""
app/api/routes/auth.py

Authentication endpoints.

Routes:
  POST /api/v1/auth/register   — create account, returns tokens
  POST /api/v1/auth/login      — authenticate, returns tokens
  POST /api/v1/auth/refresh    — rotate refresh token, returns new token pair
  POST /api/v1/auth/logout     — revoke session
  GET  /api/v1/auth/me         — current user info
  PATCH /api/v1/auth/me        — update profile
  POST /api/v1/auth/change-password — change password
  GET  /api/v1/auth/me/notifications — get notification prefs
  PUT  /api/v1/auth/me/notifications — update notification prefs
  POST /api/v1/auth/google     — Google OAuth login
  GET  /api/v1/auth/google/url — get Google OAuth URL
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.middleware.rate_limiter import rate_limit
from app.dependencies import DB, CurrentUser
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,

    UpdateProfileRequest,
    ChangePasswordRequest,
)
from app.services.auth.auth_service import AuthError, AuthService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _service(db: DB) -> AuthService:
    return AuthService(db=db)


def _auth_error_to_http(e: AuthError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)


# ── Response models for previously untyped endpoints ─────────────────────────

class NotificationPrefsResponse(BaseModel):
    notification_preferences: dict

class GoogleAuthUrlResponse(BaseModel):
    auth_url: str


# ── Register ──────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterResponse,
    summary="Create a new account",
)
async def register(
    payload: RegisterRequest,
    db: DB,
    _rl: None = Depends(rate_limit("register", max_calls=5, window_seconds=60)),
) -> RegisterResponse:
    svc = _service(db)
    try:
        user = await svc.register(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )
        # Persist user first so registration cannot be blocked by downstream services.
        await db.commit()

        # Auto-login after registration
        _, access_token, refresh_token = await svc.login(
            email=payload.email,
            password=payload.password,
        )
        await db.commit()

        # Provision free subscription (non-fatal). Use a SAVEPOINT so failures
        # roll back only the subscription insert — never session.rollback(), which
        # expires the User instance and causes 500s when building RegisterResponse.
        try:
            async with db.begin_nested():
                from app.services.billing.billing_service import BillingService

                billing = BillingService(db=db)
                await billing.provision_free_subscription(user.id)
        except Exception as _e:
            logger.warning("provision_free_subscription_failed", error=str(_e))
        else:
            await db.commit()

        await db.refresh(user)

        # Send verification email (non-fatal)
        try:
            from app.services.email.service import get_email_service
            from app.services.email.tokens import generate_token
            token = generate_token(user.id, "verify")
            get_email_service().send_verification_email(
                to_email=user.email,
                to_name=user.full_name,
                token=token,
            )
        except Exception as _e:
            logger.warning("verify_email_send_failed", error=str(_e))

    except AuthError as e:
        raise _auth_error_to_http(e)

    return RegisterResponse(
        user=UserResponse.model_validate(user),
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive tokens",
)
async def login(
    payload: LoginRequest,
    db: DB,
    _rl: None = Depends(rate_limit("login", max_calls=10, window_seconds=60)),
) -> TokenResponse:
    svc = _service(db)
    try:
        _, access_token, refresh_token = await svc.login(
            email=payload.email,
            password=payload.password,
        )
        await db.commit()
    except AuthError as e:
        raise _auth_error_to_http(e)

    return TokenResponse.from_tokens(access_token, refresh_token)


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and get new access token",
)
async def refresh(
    payload: RefreshRequest,
    db: DB,
    _rl: None = Depends(rate_limit("refresh", max_calls=20, window_seconds=60)),
) -> TokenResponse:
    svc = _service(db)
    try:
        access_token, refresh_token = await svc.refresh(payload.refresh_token)
        await db.commit()
    except AuthError as e:
        raise _auth_error_to_http(e)

    return TokenResponse.from_tokens(access_token, refresh_token)


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke current session",
)
async def logout(db: DB, current_user: CurrentUser) -> MessageResponse:
    svc = _service(db)
    await svc.logout(current_user.id)
    await db.commit()
    return MessageResponse(message="Logged out successfully.")


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user info",
)
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


# ── Update profile ────────────────────────────────────────────────────────────

@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
)
async def update_me(
    payload: UpdateProfileRequest,
    db: DB,
    current_user: CurrentUser,
) -> UserResponse:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    await db.flush()
    await db.commit()
    return UserResponse.model_validate(current_user)


class NotificationPrefsRequest(BaseModel):
    pack_complete_email: bool | None = None
    scout_digest_email: bool | None = None
    hidden_market_email: bool | None = None
    shadow_ready_email: bool | None = None


@router.put(
    "/me/notifications",
    response_model=NotificationPrefsResponse,
    summary="Update notification preferences",
)
async def update_notification_preferences(
    payload: NotificationPrefsRequest,
    db: DB,
    current_user: CurrentUser,
) -> NotificationPrefsResponse:
    current = dict(current_user.notification_preferences or {})
    updates = payload.model_dump(exclude_none=True)
    current.update(updates)
    # Assign a new dict to force SQLAlchemy JSONB mutation detection
    current_user.notification_preferences = dict(current)
    await db.flush()
    await db.commit()
    return NotificationPrefsResponse(notification_preferences=current_user.notification_preferences)


@router.get(
    "/me/notifications",
    response_model=NotificationPrefsResponse,
    summary="Get notification preferences",
)
async def get_notification_preferences(current_user: CurrentUser) -> NotificationPrefsResponse:
    prefs = current_user.notification_preferences or {
        "pack_complete_email": True,
        "scout_digest_email": True,
        "hidden_market_email": True,
        "shadow_ready_email": True,
    }
    return NotificationPrefsResponse(notification_preferences=prefs)


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password",
)
async def change_password(
    payload: ChangePasswordRequest,
    db: DB,
    current_user: CurrentUser,
) -> MessageResponse:
    # OAuth users don't have a password — block change-password
    if current_user.password_hash == "OAUTH_NO_PASSWORD":
        raise HTTPException(
            status_code=400,
            detail="Password change is not available for accounts created via Google login. "
                   "Use your Google account to sign in.",
        )

    # Verify current password
    from app.services.auth.password import hash_password, verify_password
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = hash_password(payload.new_password)
    await db.flush()
    await db.commit()
    return MessageResponse(message="Password updated successfully.")


# ── Social / OAuth Login ─────────────────────────────────────────────────────

class GoogleLoginRequest(BaseModel):
    """Frontend sends the Google OAuth code after redirect."""
    code: str
    redirect_uri: str | None = None  # Frontend can override


class OAuthLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool
    user: UserResponse


@router.post(
    "/google",
    response_model=OAuthLoginResponse,
    summary="Log in or register via Google OAuth",
)
async def google_login(
    payload: GoogleLoginRequest,
    db: DB,
    _rl: None = Depends(rate_limit("google_oauth", max_calls=10, window_seconds=60)),
) -> OAuthLoginResponse:
    """
    Exchange a Google OAuth code for StealthRole tokens.
    Auto-creates account if user doesn't exist.
    """
    from app.config import settings
    import httpx

    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google login not configured")

    redirect_uri = payload.redirect_uri or f"{settings.app_base_url}/auth/callback"

    # Exchange code for Google tokens
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://oauth2.googleapis.com/token", data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": payload.code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            })
            resp.raise_for_status()
            google_tokens = resp.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google OAuth failed: {e}")

    # Get user info from Google
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {google_tokens['access_token']}"},
            )
            resp.raise_for_status()
            user_info = resp.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to get Google user info")

    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="No email from Google")

    full_name = user_info.get("name")

    svc = _service(db)
    try:
        user, access_token, refresh_token, is_new = await svc.oauth_login(
            email=email, full_name=full_name, provider="google",
        )
        await db.commit()
    except AuthError as e:
        raise _auth_error_to_http(e)

    return OAuthLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        is_new_user=is_new,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/google/url",
    response_model=GoogleAuthUrlResponse,
    summary="Get Google OAuth URL for login",
)
async def google_login_url() -> GoogleAuthUrlResponse:
    """Return the Google OAuth consent URL for the frontend to redirect to."""
    from app.config import settings
    import httpx

    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google login not configured")

    redirect_uri = f"{settings.app_base_url}/auth/callback"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": "google_login",
    }
    url = str(httpx.URL("https://accounts.google.com/o/oauth2/v2/auth", params=params))
    return GoogleAuthUrlResponse(auth_url=url)
