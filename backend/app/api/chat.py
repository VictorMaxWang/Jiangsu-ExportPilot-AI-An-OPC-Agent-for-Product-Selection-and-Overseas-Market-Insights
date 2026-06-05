from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.ai import get_bailian_client
from app.db import get_db
from app.models import ChatMessage, ChatSession
from app.schemas import (
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageRead,
    ChatMessageSendResponse,
    ChatSessionCreate,
    ChatSessionListResponse,
    ChatSessionRead,
    ReportEditProposalRead,
)
from app.services.ai import BailianClient
from app.services.chat_service import ChatInputError, ChatNotFoundError, ChatSendOutcome, ChatService


router = APIRouter()


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


@router.post("/sessions", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    payload: ChatSessionCreate,
    service: ChatService = Depends(get_chat_service),
) -> ChatSessionRead:
    try:
        return _session_read(service.create_session(payload))
    except ChatNotFoundError as exc:
        raise _not_found(exc) from exc
    except ChatInputError as exc:
        raise _unprocessable(exc) from exc


@router.get("/sessions", response_model=ChatSessionListResponse)
def list_chat_sessions(
    report_id: int | None = Query(default=None, ge=1),
    analysis_id: int | None = Query(default=None, ge=1),
    product_id: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    service: ChatService = Depends(get_chat_service),
) -> ChatSessionListResponse:
    sessions, total = service.list_sessions(
        skip=skip,
        limit=limit,
        report_id=report_id,
        analysis_id=analysis_id,
        product_id=product_id,
        status=status_filter,
    )
    return ChatSessionListResponse(items=[_session_read(session) for session in sessions], total=total)


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageSendResponse)
async def send_chat_message(
    session_id: int,
    payload: ChatMessageCreate,
    service: ChatService = Depends(get_chat_service),
    ai_client: BailianClient = Depends(get_bailian_client),
) -> ChatMessageSendResponse:
    try:
        outcome = await service.send_message(session_id, payload, ai_client)
    except ChatNotFoundError as exc:
        raise _not_found(exc) from exc
    except ChatInputError as exc:
        raise _unprocessable(exc) from exc
    return _send_response(outcome)


@router.get("/sessions/{session_id}/messages", response_model=ChatMessageListResponse)
def list_chat_messages(
    session_id: int,
    service: ChatService = Depends(get_chat_service),
) -> ChatMessageListResponse:
    try:
        messages = service.list_messages(session_id)
    except ChatNotFoundError as exc:
        raise _not_found(exc) from exc
    return ChatMessageListResponse(items=[_message_read(message) for message in messages], total=len(messages))


def _send_response(outcome: ChatSendOutcome) -> ChatMessageSendResponse:
    return ChatMessageSendResponse(
        session=_session_read(outcome.session),
        user_message=_message_read(outcome.user_message),
        assistant_message=_message_read(outcome.assistant_message),
        proposal=ReportEditProposalRead.model_validate(outcome.proposal) if outcome.proposal is not None else None,
    )


def _session_read(session: ChatSession) -> ChatSessionRead:
    payload = ChatSessionRead.model_validate(session)
    page_context = None
    if isinstance(session.context_refs, dict) and isinstance(session.context_refs.get("page_context"), dict):
        page_context = session.context_refs["page_context"]
    return payload.model_copy(update={"page_context": page_context})


def _message_read(message: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead.model_validate(message)


def _not_found(exc: ChatNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code, "message": str(exc)})


def _unprocessable(exc: ChatInputError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code, "message": str(exc)})
