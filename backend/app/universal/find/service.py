"""Orchestration for clarify → search → refine."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.email_agent.json_utils import parse_json_response
from app.ai.config import settings as ai_settings
from app.ai.openai_client import chat_messages
from app.ai.tools.tavily import SearchResult, web_search
from app.db.find_feedback import log_feedback_event
from app.db.find_sessions import (
    append_message,
    derive_title,
    get_session,
    list_messages,
    load_session_state,
    reset_session as db_reset_session,
    save_session_state,
    touch_session_title,
)
from app.universal.find.models import (
    FindMessageFeedback,
    FindRequest,
    FindResult,
    FindSessionState,
    FindTurnResponse,
    RefineFeedback,
    ThumbFeedback,
)
from app.universal.find.prompts import (
    BUILD_QUERY_SYSTEM,
    EXTRACT_REQUEST_SYSTEM,
    FILTER_RESULTS_SYSTEM,
    REFINE_SYSTEM,
)

logger = logging.getLogger(__name__)

MAX_CLARIFICATION_ROUNDS = 5
MAX_RESULTS = 5


def _call_llm_json(system: str, user: str, *, max_tokens: int = 800) -> dict[str, Any]:
    if not ai_settings.openai_configured:
        raise ValueError("OpenAI API key is not configured")

    response = chat_messages(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
    )
    try:
        return parse_json_response(response)
    except json.JSONDecodeError as exc:
        logger.warning("LLM JSON parse failed, retrying once: %s", exc)
        retry = chat_messages(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": response},
                {"role": "user", "content": "Reply with valid JSON only. No markdown."},
            ],
            max_tokens=max_tokens,
        )
        return parse_json_response(retry)


def _format_conversation(messages: list) -> str:
    lines: list[str] = []
    for index, msg in enumerate(messages, start=1):
        role = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{index}. {role}: {msg.content}")
    return "\n".join(lines) if lines else "(no messages yet)"


def _build_extract_user_prompt(
    messages: list,
    current_request: FindRequest | None,
) -> str:
    accumulated = (
        json.dumps(current_request.model_dump(), indent=2)
        if current_request
        else "{}"
    )
    return (
        f"Conversation:\n{_format_conversation(messages)}\n\n"
        f"Current accumulated request (may be empty on first turn):\n{accumulated}\n\n"
        "Return updated JSON."
    )


def _parse_find_request(data: dict[str, Any]) -> FindRequest:
    raw_status = data.get("status")
    status = raw_status if raw_status in ("ready", "needs_clarification") else "needs_clarification"
    return FindRequest(
        subject=str(data.get("subject") or "unspecified item").strip(),
        constraints=dict(data.get("constraints") or {}),
        status=status,
        missing=list(data.get("missing") or []),
        clarifying_question=data.get("clarifying_question"),
    )


def _search_results_to_find(results: list[SearchResult]) -> list[FindResult]:
    return [
        FindResult(
            index=index,
            title=result.title,
            snippet=result.snippet,
            url=result.url,
            image_url=result.image_url,
        )
        for index, result in enumerate(results, start=1)
    ]


async def _filter_results(
    request: FindRequest,
    results: list[FindResult],
) -> list[FindResult]:
    """Filter out irrelevant or non-specific results using LLM."""
    if not results:
        return results

    filter_prompt = f"""User request:
Subject: {request.subject}
Constraints: {json.dumps(request.constraints, indent=2)}

Results to evaluate:
{json.dumps([
    {
        "index": i,
        "title": r.title,
        "url": r.url,
        "snippet": r.snippet[:200]
    }
    for i, r in enumerate(results)
], indent=2)}

Evaluate each result and determine which to keep vs drop."""

    try:
        data = _call_llm_json(FILTER_RESULTS_SYSTEM, filter_prompt, max_tokens=1000)
        filtered_data = data.get("filtered", [])

        # Create a map of index to keep decision
        keep_map = {item["index"]: item.get("keep", False) for item in filtered_data}

        # Filter results based on LLM decision
        kept_results = [r for i, r in enumerate(results) if keep_map.get(i, False)]

        logger.info(
            f"Filtered {len(results)} results down to {len(kept_results)} "
            f"for request: {request.subject}"
        )

        return kept_results
    except Exception as exc:
        logger.warning(f"Filter failed, returning all results: {exc}")
        return results


def _run_search(query: str) -> tuple[str, list[FindResult]]:
    if not ai_settings.tavily_configured:
        raise ValueError("Tavily API key is not configured")
    raw = web_search(query, max_results=MAX_RESULTS, include_images=True)
    return query, _search_results_to_find(raw)


async def _run_filtered_search(request: FindRequest, query: str) -> tuple[str, list[FindResult]]:
    """Run search with relevance filtering and optional backfill."""
    search_query, raw_results = _run_search(query)
    filtered = await _filter_results(request, raw_results)

    # If we have fewer than 3 results, do one backfill search
    if len(filtered) < 3 and len(filtered) < len(raw_results):
        logger.info(f"Only {len(filtered)} results after filtering, attempting backfill")
        # Create a more specific query by appending terms
        backfill_query = f"{query} specific product"
        _, backfill_results = _run_search(backfill_query)
        backfill_filtered = await _filter_results(request, backfill_results)

        # Combine results, avoiding duplicates by URL
        seen_urls = {r.url for r in filtered}
        for result in backfill_filtered:
            if result.url not in seen_urls and len(filtered) < MAX_RESULTS:
                filtered.append(result)
                seen_urls.add(result.url)

        logger.info(f"After backfill: {len(filtered)} total results")

    # Re-index results to be sequential starting from 1
    for i, result in enumerate(filtered, start=1):
        result.index = i

    return search_query, filtered


def _build_query(request: FindRequest) -> str:
    data = _call_llm_json(
        BUILD_QUERY_SYSTEM,
        json.dumps({"subject": request.subject, "constraints": request.constraints}),
    )
    query = str(data.get("query") or "").strip()
    if not query:
        parts = [request.subject]
        for key, value in request.constraints.items():
            parts.append(f"{key} {value}")
        query = " ".join(parts)
    return query


def _results_intro(request: FindRequest, count: int) -> str:
    if count == 0:
        return (
            f"I couldn't find strong matches for {request.subject}. "
            "Try broadening your request or changing a constraint."
        )
    return f"Here are {count} options for {request.subject}:"


def _assistant_payload(
    request: FindRequest | None,
    results: list[FindResult],
    query: str | None,
) -> dict[str, Any]:
    return {
        "request": request.model_dump() if request else None,
        "results": [r.model_dump() for r in results],
        "query": query,
    }


def _turn_response(session_id: str, state: FindSessionState, assistant_message: str | None) -> FindTurnResponse:
    return FindTurnResponse(
        session_id=session_id,
        phase=state.phase,
        assistant_message=assistant_message,
        request=state.request,
        results=state.last_results,
        messages=list_messages(session_id),
    )


def extract_request(messages: list, current: FindRequest | None) -> FindRequest:
    data = _call_llm_json(
        EXTRACT_REQUEST_SYSTEM,
        _build_extract_user_prompt(messages, current),
    )
    return _parse_find_request(data)


def refine_request(
    request: FindRequest,
    results: list[FindResult],
    user_feedback: str,
    feedback_meta: dict[str, Any] | None,
) -> tuple[FindRequest, str, str]:
    payload = {
        "request": request.model_dump(),
        "results": [r.model_dump() for r in results],
        "user_feedback": user_feedback,
        "feedback_meta": feedback_meta,
    }
    data = _call_llm_json(REFINE_SYSTEM, json.dumps(payload))
    updated = _parse_find_request(data.get("request") or {})
    query = str(data.get("query") or "").strip()
    if not query:
        query = _build_query(updated)
    assistant_message = str(data.get("assistant_message") or "Searching with your feedback…").strip()
    return updated, query, assistant_message


async def handle_message(
    session_id: str,
    *,
    message: str = "",
    feedback: FindMessageFeedback = None,
) -> FindTurnResponse:
    row = get_session(session_id)
    if row is None:
        raise ValueError(f"Session not found: {session_id}")

    state = load_session_state(session_id)
    clarification_rounds = int(row.get("clarification_rounds") or 0)
    prior_request = state.request.model_copy(deep=True) if state.request else None

    user_content = message.strip()
    if feedback is not None:
        if isinstance(feedback, ThumbFeedback):
            thumb_label = "liked" if feedback.value == "up" else "disliked"
            user_content = user_content or f"{thumb_label} result #{feedback.index}"
        elif isinstance(feedback, RefineFeedback):
            # Format batch ratings into readable text
            ups = [r["index"] for r in feedback.ratings if r.get("value") == "up"]
            downs = [r["index"] for r in feedback.ratings if r.get("value") == "down"]
            parts = []
            if ups:
                parts.append(f"liked results {', '.join(f'#{i}' for i in ups)}")
            if downs:
                parts.append(f"disliked results {', '.join(f'#{i}' for i in downs)}")
            user_content = user_content or "; ".join(parts)

    if not user_content:
        raise ValueError("Message or feedback is required")

    append_message(session_id, role="user", content=user_content)

    if state.phase == "gathering":
        messages = list_messages(session_id)
        request = extract_request(messages, state.request)

        if request.status == "needs_clarification" and clarification_rounds >= MAX_CLARIFICATION_ROUNDS:
            request.status = "ready"
            request.missing = []
            request.clarifying_question = None

        state.request = request
        touch_session_title(session_id, request.subject)

        if request.status == "needs_clarification":
            question = request.clarifying_question or "Could you share a bit more detail?"
            append_message(
                session_id,
                role="assistant",
                content=question,
                payload={"request": request.model_dump()},
            )
            clarification_rounds += 1
            save_session_state(
                session_id,
                state,
                title=derive_title(request.subject),
                clarification_rounds=clarification_rounds,
            )
            log_feedback_event(
                session_id=session_id,
                event_type="clarification",
                user_message=user_content,
                request_before=prior_request.model_dump() if prior_request else None,
                request_after=request.model_dump(),
            )
            return _turn_response(session_id, state, question)

        query = _build_query(request)
        search_query, results = await _run_filtered_search(request, query)
        intro = _results_intro(request, len(results))

        state.phase = "results"
        state.request = request
        state.last_query = search_query
        state.last_results = results
        append_message(
            session_id,
            role="assistant",
            content=intro,
            payload=_assistant_payload(request, results, search_query),
        )
        save_session_state(
            session_id,
            state,
            title=derive_title(request.subject),
            clarification_rounds=clarification_rounds,
        )
        log_feedback_event(
            session_id=session_id,
            event_type="search",
            user_message=user_content,
            request_before=prior_request.model_dump() if prior_request else None,
            request_after=request.model_dump(),
            results_shown=[r.model_dump() for r in results],
            search_query=search_query,
        )
        return _turn_response(session_id, state, intro)

    # phase == results — refine and re-search
    if state.request is None:
        state.phase = "gathering"
        save_session_state(session_id, state)
        return await handle_message(session_id, message=user_content)

    feedback_meta = feedback.model_dump() if feedback else None
    updated, query, intro = refine_request(
        state.request,
        state.last_results,
        user_content,
        feedback_meta,
    )
    search_query, results = await _run_filtered_search(updated, query)
    if not results:
        intro = _results_intro(updated, 0)

    # Determine event type based on feedback type
    event_type = "refinement"
    if feedback:
        if isinstance(feedback, ThumbFeedback):
            event_type = "thumb"
        elif isinstance(feedback, RefineFeedback):
            event_type = "batch_rating"

    log_feedback_event(
        session_id=session_id,
        event_type=event_type,
        user_message=user_content,
        request_before=state.request.model_dump(),
        request_after=updated.model_dump(),
        results_shown=[r.model_dump() for r in state.last_results],
        search_query=search_query,
        metadata=feedback_meta or {},
    )

    state.request = updated
    state.last_query = search_query
    state.last_results = results
    append_message(
        session_id,
        role="assistant",
        content=intro,
        payload=_assistant_payload(updated, results, search_query),
    )
    save_session_state(session_id, state, title=derive_title(updated.subject))
    return _turn_response(session_id, state, intro)


def get_session_response(session_id: str) -> FindTurnResponse:
    row = get_session(session_id)
    if row is None:
        raise ValueError(f"Session not found: {session_id}")
    state = load_session_state(session_id)
    last_assistant = next(
        (m.content for m in reversed(list_messages(session_id)) if m.role == "assistant"),
        None,
    )
    return _turn_response(session_id, state, last_assistant)


def reset_session(session_id: str) -> FindTurnResponse:
    row = get_session(session_id)
    if row is None:
        raise ValueError(f"Session not found: {session_id}")
    state = db_reset_session(session_id)
    return FindTurnResponse(
        session_id=session_id,
        phase=state.phase,
        assistant_message=None,
        request=None,
        results=[],
        messages=list_messages(session_id),
    )
