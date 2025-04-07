"""Authentication and authorization endpoints for the API.

This module provides endpoints for user registration, login, session management,
and token verification.
"""

import uuid
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.config import settings
from app.core.langgraph.graph import LangGraphAgent
from app.core.limiter import limiter
from app.core.logging import (
    bind_context,
    logger,
)
from app.models.session import Session
from app.models.user import User
from app.schemas.auth import (
    SessionResponse,
    TokenResponse,
    UserCreate,
    UserProfileResponse,
    UserResponse,
)
from app.services.database import database_service
from app.utils.auth import (
    create_access_token,
    verify_token,
)
from app.utils.sanitization import (
    sanitize_email,
    sanitize_string,
    validate_password_strength,
)

router = APIRouter()
security = HTTPBearer()
# Reuse the shared instance: DatabaseService.__init__ builds its own engine, so a
# second instance here meant two independent connection pools.
db_service = database_service
agent = LangGraphAgent()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """Get the current user ID from the token.

    Args:
        credentials: The HTTP authorization credentials containing the JWT token.

    Returns:
        User: The user extracted from the token.

    Raises:
        HTTPException: If the token is invalid or missing.
    """
    try:
        # Sanitize token
        token = sanitize_string(credentials.credentials)

        user_id = verify_token(token)
        if user_id is None:
            logger.error("invalid_token", token_part=token[:10] + "...")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify user exists in database
        user_id_int = int(user_id)
        user = await db_service.get_user(user_id_int)
        if user is None:
            logger.error("user_not_found", user_id=user_id_int)
            raise HTTPException(
                status_code=404,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Bind user_id to logging context for all subsequent logs in this request
        bind_context(user_id=user_id_int)

        return user
    except ValueError as ve:
        logger.exception("token_validation_failed", error=str(ve))
        raise HTTPException(
            status_code=422,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Session:
    """Get the current session ID from the token.

    Args:
        credentials: The HTTP authorization credentials containing the JWT token.

    Returns:
        Session: The session extracted from the token.

    Raises:
        HTTPException: If the token is invalid or missing.
    """
    try:
        # Sanitize token
        token = sanitize_string(credentials.credentials)

        session_id = verify_token(token)
        if session_id is None:
            logger.error("session_id_not_found", token_part=token[:10] + "...")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Sanitize session_id before using it
        session_id = sanitize_string(session_id)

        # Verify session exists in database
        session = await db_service.get_session(session_id)
        if session is None:
            logger.error("session_not_found", session_id=session_id)
            raise HTTPException(
                status_code=404,
                detail="Session not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Bind user_id to logging context for all subsequent logs in this request
        bind_context(user_id=session.user_id)

        return session
    except ValueError as ve:
        logger.exception("token_validation_failed", error=str(ve))
        raise HTTPException(
            status_code=422,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=UserProfileResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get profile information for the current authenticated user.

    Args:
        user: The authenticated user from token

    Returns:
        UserProfileResponse: The user's ID, email, and display name
    """
    return UserProfileResponse(id=user.id, email=user.email, username=user.username)


@router.post("/guest", response_model=SessionResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["guest"][0])
async def create_guest_session(request: Request):
    """Create an anonymous guest chat session without login.

    Gets or creates a shared guest user, then opens a fresh session.

    Returns:
        SessionResponse: Session ID and access token for chatbot APIs.
    """
    guest_email = "guest@math-teacher.local"
    try:
        user = await db_service.get_user_by_email(guest_email)
        if user is None:
            user = await db_service.create_user(
                email=guest_email,
                password=User.hash_password("Guest!MathTeacher9"),
                username="访客",
            )
            logger.info("guest_user_created", user_id=user.id)

        session_id = str(uuid.uuid4())
        session = await db_service.create_session(session_id, user.id, username=user.username)
        token = create_access_token(session_id)

        logger.info("guest_session_created", session_id=session_id, user_id=user.id)
        return SessionResponse(
            session_id=session_id,
            name=session.name,
            token=token,
            created_at=session.created_at,
        )
    except Exception as e:
        logger.exception("guest_session_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create guest session")


@router.post("/register", response_model=UserResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["register"][0])
async def register_user(request: Request, user_data: UserCreate):
    """Register a new user.

    Args:
        request: The FastAPI request object for rate limiting.
        user_data: User registration data

    Returns:
        UserResponse: The created user info
    """
    try:
        # Sanitize email
        sanitized_email = sanitize_email(user_data.email)

        # Extract and validate password
        password = user_data.password.get_secret_value()
        validate_password_strength(password)

        # Check if user exists
        if await db_service.get_user_by_email(sanitized_email):
            raise HTTPException(status_code=400, detail="Email already registered")

        # Sanitize optional username
        sanitized_username = sanitize_string(user_data.username) if user_data.username else None

        # Create user
        user = await db_service.create_user(
            email=sanitized_email,
            password=User.hash_password(password),
            username=sanitized_username,
        )

        # Create access token
        token = create_access_token(str(user.id))

        return UserResponse(id=user.id, email=user.email, username=user.username, token=token)
    except ValueError as ve:
        logger.exception("user_registration_validation_failed", error=str(ve))
        raise HTTPException(status_code=422, detail=str(ve))


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["login"][0])
async def login(
    request: Request,
):
    """Login a user supporting JSON body and form-encoded data.

    Args:
        request: The FastAPI request object

    Returns:
        TokenResponse: Access token information

    Raises:
        HTTPException: If credentials are invalid
    """
    try:
        content_type = request.headers.get("content-type", "")
        raw_email = None
        raw_password = None
        grant_type = "password"

        if "application/json" in content_type:
            data = await request.json()
            raw_email = data.get("email")
            raw_password = data.get("password")
            grant_type = data.get("grant_type", "password")
        else:
            form = await request.form()
            raw_email = form.get("email")
            raw_password = form.get("password")
            grant_type = str(form.get("grant_type", "password"))

        if not raw_email or not raw_password:
            raise HTTPException(status_code=422, detail="Email and password are required")

        email = sanitize_string(str(raw_email))
        password = str(raw_password)
        grant_type = sanitize_string(str(grant_type))

        # Verify grant type
        if grant_type != "password":
            raise HTTPException(
                status_code=400,
                detail="Unsupported grant type. Must be 'password'",
            )

        user = await db_service.get_user_by_email(email)
        if not user or not user.verify_password(password):
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = create_access_token(str(user.id))
        return TokenResponse(access_token=token.access_token, token_type="bearer", expires_at=token.expires_at)
    except HTTPException:
        raise
    except ValueError as ve:
        logger.exception("login_validation_failed", error=str(ve))
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.exception("login_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/session", response_model=SessionResponse)
async def create_session(user: User = Depends(get_current_user)):
    """Create a new chat session for the authenticated user.

    Args:
        user: The authenticated user

    Returns:
        SessionResponse: The session ID, name, and access token
    """
    try:
        # Generate a unique session ID
        session_id = str(uuid.uuid4())

        # Create session in database, copying username for LLM personalization
        session = await db_service.create_session(session_id, user.id, username=user.username)

        # Create access token for the session
        token = create_access_token(session_id)

        logger.info(
            "session_created",
            session_id=session_id,
            user_id=user.id,
            name=session.name,
            expires_at=token.expires_at.isoformat(),
        )

        return SessionResponse(
            session_id=session_id,
            name=session.name,
            token=token,
            created_at=session.created_at,
        )
    except ValueError as ve:
        logger.exception("session_creation_validation_failed", error=str(ve), user_id=user.id)
        raise HTTPException(status_code=422, detail=str(ve))


@router.patch("/session/{session_id}/name", response_model=SessionResponse)
async def update_session_name(
    session_id: str,
    name: str = Form(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Update a session's name.

    Args:
        session_id: The ID of the session to update
        name: The new name for the session
        credentials: The auth token (user token or session token)

    Returns:
        SessionResponse: The updated session information
    """
    try:
        sanitized_session_id = sanitize_string(session_id)
        sanitized_name = sanitize_string(name)
        token = sanitize_string(credentials.credentials)
        token_sub = verify_token(token)
        if not token_sub:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        session = await db_service.get_session(sanitized_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        is_owner = token_sub == sanitized_session_id
        if not is_owner:
            try:
                user_id = int(token_sub)
                if session.user_id == user_id:
                    is_owner = True
            except ValueError:
                pass

        if not is_owner:
            raise HTTPException(status_code=403, detail="Cannot modify other sessions")

        updated_session = await db_service.update_session_name(sanitized_session_id, sanitized_name)
        token_resp = create_access_token(sanitized_session_id)

        return SessionResponse(
            session_id=sanitized_session_id,
            name=updated_session.name,
            token=token_resp,
            created_at=updated_session.created_at,
        )
    except HTTPException:
        raise
    except ValueError as ve:
        logger.exception("session_update_validation_failed", error=str(ve), session_id=session_id)
        raise HTTPException(status_code=422, detail=str(ve))


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Delete a session for the authenticated user or session holder.

    Args:
        session_id: The ID of the session to delete
        credentials: The auth credentials

    Returns:
        dict: Success message
    """
    try:
        sanitized_session_id = sanitize_string(session_id)
        token = sanitize_string(credentials.credentials)
        token_sub = verify_token(token)
        if not token_sub:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        session = await db_service.get_session(sanitized_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        is_owner = token_sub == sanitized_session_id
        if not is_owner:
            try:
                user_id = int(token_sub)
                if session.user_id == user_id:
                    is_owner = True
            except ValueError:
                pass

        if not is_owner:
            raise HTTPException(status_code=403, detail="Cannot delete other sessions")

        await db_service.delete_session(sanitized_session_id)

        # Clear checkpoint history
        try:
            await agent.clear_chat_history(sanitized_session_id)
        except Exception as ce:
            logger.warning("checkpoint_clear_on_delete_failed", session_id=sanitized_session_id, error=str(ce))

        logger.info("session_deleted", session_id=session_id, user_id=session.user_id)
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except ValueError as ve:
        logger.exception("session_deletion_validation_failed", error=str(ve), session_id=session_id)
        raise HTTPException(status_code=422, detail=str(ve))


@router.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(user: User = Depends(get_current_user)):
    """Get all session IDs for the authenticated user.

    Args:
        user: The authenticated user

    Returns:
        List[SessionResponse]: List of session IDs
    """
    try:
        sessions = await db_service.get_user_sessions(user.id)
        return [
            SessionResponse(
                session_id=sanitize_string(session.id),
                name=sanitize_string(session.name) if session.name else "新会话",
                token=create_access_token(session.id),
                created_at=session.created_at,
            )
            for session in sessions
        ]
    except ValueError as ve:
        logger.exception("get_sessions_validation_failed", user_id=user.id, error=str(ve))
        raise HTTPException(status_code=422, detail=str(ve))
