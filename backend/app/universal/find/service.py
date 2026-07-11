"""Orchestration for clarify → search → refine."""

from __future__ import annotations

import json
import logging
import re
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
    RatingRecord,
    RefineFeedback,
    ThumbFeedback,
)
from app.universal.find.prompts import (
    BUILD_QUERY_SYSTEM,
    EXTRACT_PREFERENCES_SYSTEM,
    EXTRACT_REQUEST_SYSTEM,
    FILTER_RESULTS_SYSTEM,
    REFINE_QUERY_SYSTEM,
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


def _extract_preference_patterns(
    all_ratings: list[RatingRecord],
) -> tuple[list[str], list[str]]:
    """Extract liked/disliked attribute patterns from accumulated ratings."""
    if len(all_ratings) < 3:
        return [], []

    ratings_data = [
        {
            "turn": r.turn,
            "value": r.value,
            "title": r.title,
            "snippet": r.snippet[:150],
            "url": r.url,
        }
        for r in all_ratings
    ]
    try:
        data = _call_llm_json(
            EXTRACT_PREFERENCES_SYSTEM,
            json.dumps(ratings_data),
            max_tokens=500,
        )
        liked = list(data.get("liked_attributes") or [])
        disliked = list(data.get("disliked_attributes") or [])
        summary = data.get("summary", "")
        print(f"\n🧠 FIND: Extracted preferences from {len(all_ratings)} ratings:")
        print(f"   Liked: {liked}")
        print(f"   Disliked: {disliked}")
        print(f"   Summary: {summary}")
        return liked, disliked
    except Exception as exc:
        logger.warning(f"Preference extraction failed: {exc}")
        return [], []


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


# URL patterns that are unambiguously catalog/listing pages (not product pages)
_CATALOG_URL_PATTERNS = [
    re.compile(r"amazon\.com/.*/s\?"),          # Amazon search/listing pages
    re.compile(r"/s\?keywords="),                # Amazon-style search params
    re.compile(r"[?&]rh=n%3A"),                  # Amazon category browse
    re.compile(r"/catpage[-/]"),                  # explicit catalog pages
    re.compile(r"/browse/"),                      # browse pages
]


def _is_obvious_catalog_url(url: str) -> bool:
    """Fast check for URLs that are unambiguously catalog/listing pages."""
    return any(p.search(url) for p in _CATALOG_URL_PATTERNS)


async def _filter_results(
    request: FindRequest,
    results: list[FindResult],
) -> list[FindResult]:
    """Filter out irrelevant or non-specific results using LLM."""
    if not results:
        return results

    # Pre-filter: drop unambiguous catalog URLs before LLM call
    pre_filtered = []
    for r in results:
        if _is_obvious_catalog_url(r.url):
            print(f"  ✗ Pre-filter DROP (catalog URL): {r.title[:60]}")
            print(f"          URL: {r.url[:80]}")
        else:
            pre_filtered.append(r)

    if not pre_filtered:
        print("⚠️  FIND: Pre-filter dropped everything, falling back to raw results")
        pre_filtered = results[:3]

    results = pre_filtered

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

        # Create a map of index to keep decision with reasons
        keep_map = {
            item["index"]: {
                "keep": item.get("keep", False),
                "reason": item.get("reason", "")
            }
            for item in filtered_data
        }

        # Log each result and filter decision
        print(f"\n=== FILTER RESULTS for '{request.subject}' ===")
        print(f"Evaluating {len(results)} results:")
        for i, r in enumerate(results):
            decision = keep_map.get(i, {})
            kept = decision.get("keep", False)
            reason = decision.get("reason", "no reason given")
            status = "✓ KEEP" if kept else "✗ DROP"
            print(f"  [{status}] #{i+1}: {r.title[:60]}")
            print(f"          URL: {r.url[:80]}")
            print(f"          Reason: {reason}")

        # Filter results based on LLM decision
        kept_results = [r for i, r in enumerate(results) if keep_map.get(i, {}).get("keep", False)]

        print(f"=== FINAL: Kept {len(kept_results)} of {len(results)} results ===\n")

        return kept_results
    except Exception as exc:
        logger.warning(f"Filter failed, returning all results: {exc}")
        return results


def _run_search(query: str) -> tuple[str, list[FindResult]]:
    if not ai_settings.tavily_configured:
        raise ValueError("Tavily API key is not configured")
    print(f"\n🔍 FIND: Searching Tavily with query: '{query}'")
    raw = web_search(query, max_results=MAX_RESULTS, include_images=True)
    results = _search_results_to_find(raw)
    print(f"📊 FIND: Tavily returned {len(results)} results")
    return query, results


async def _run_filtered_search(request: FindRequest, query: str) -> tuple[str, list[FindResult]]:
    """Run search with relevance filtering and optional backfill."""
    search_query, raw_results = _run_search(query)

    # If we got 0 results from Tavily, return immediately
    if not raw_results:
        print(f"⚠️  FIND: Tavily returned 0 results for query: {query}")
        return search_query, []

    filtered = await _filter_results(request, raw_results)

    # If filtering removed ALL results, be less aggressive
    if len(filtered) == 0 and len(raw_results) > 0:
        print(
            f"⚠️  FIND: Filter dropped all {len(raw_results)} results for '{request.subject}'. "
            "Returning top 3 unfiltered results as fallback."
        )
        # Return top 3 raw results as fallback
        filtered = raw_results[:3]

    # If we have fewer than 2 results, do one backfill search
    elif len(filtered) < 2 and len(filtered) < len(raw_results):
        print(f"🔄 FIND: Only {len(filtered)} results after filtering, attempting backfill")
        # Create a more specific query using site-scoped search
        backfill_query = f"site:amazon.com {query}"
        _, backfill_results = _run_search(backfill_query)

        if backfill_results:
            backfill_filtered = await _filter_results(request, backfill_results)

            # If backfill also returns nothing, use raw backfill results
            if not backfill_filtered and backfill_results:
                print("⚠️  FIND: Backfill filter also dropped everything, using raw results")
                backfill_filtered = backfill_results[:3]

            # Combine results, avoiding duplicates by URL
            seen_urls = {r.url for r in filtered}
            for result in backfill_filtered:
                if result.url not in seen_urls and len(filtered) < MAX_RESULTS:
                    filtered.append(result)
                    seen_urls.add(result.url)

        print(f"✅ FIND: After backfill: {len(filtered)} total results")

    # Re-index results to be sequential starting from 1
    for i, result in enumerate(filtered, start=1):
        result.index = i

    return search_query, filtered


def _refine_generic_query(request: FindRequest) -> tuple[bool, list[str], str]:
    """Check if query is generic and suggest specific products if so."""
    data = _call_llm_json(
        REFINE_QUERY_SYSTEM,
        json.dumps({"subject": request.subject, "constraints": request.constraints}),
        max_tokens=500,
    )

    is_generic = data.get("is_generic", False)
    reasoning = data.get("reasoning", "")

    if is_generic:
        suggested = data.get("suggested_products", [])
        print(f"\n🤖 FIND: Query '{request.subject}' is generic")
        print(f"   Suggesting specific products: {suggested}")
        return True, suggested, reasoning
    else:
        print(f"\n✓ FIND: Query '{request.subject}' is already specific")
        return False, [], reasoning


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
    return (
        f"Here are {count} options for {request.subject}. "
        "Rate what you like and dislike, or tell me your preferences — brand, material, size, budget, etc."
    )


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
    preference_history: dict[str, Any] | None = None,
) -> tuple[FindRequest, str, str]:
    payload = {
        "request": request.model_dump(),
        "results": [r.model_dump() for r in results],
        "user_feedback": user_feedback,
        "feedback_meta": feedback_meta,
        "preference_history": preference_history,
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
    user_id: str = "default",
) -> FindTurnResponse:
    row = get_session(session_id, user_id=user_id)
    if row is None:
        raise ValueError(f"Session not found: {session_id}")

    state = load_session_state(session_id, user_id=user_id)
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

        # Check if query is generic and refine to specific products if needed
        is_generic, suggested_products, reasoning = _refine_generic_query(request)

        if is_generic and suggested_products:
            # Search for each suggested product and combine results
            all_results = []
            search_queries = []

            for product in suggested_products[:2]:  # Limit to 2 products
                product_query = f"{product} price"
                search_queries.append(product_query)
                _, product_results = await _run_filtered_search(request, product_query)
                # Add results, avoiding duplicates
                seen_urls = {r.url for r in all_results}
                for result in product_results:
                    if result.url not in seen_urls and len(all_results) < MAX_RESULTS:
                        all_results.append(result)
                        seen_urls.add(result.url)

            # Re-index results
            for i, result in enumerate(all_results, start=1):
                result.index = i

            results = all_results
            search_query = " + ".join(search_queries)
            intro = (
                f"Here are some options for {request.subject}. "
                "Rate what you like and dislike, or tell me your preferences — brand, material, size, budget, etc."
            )
        else:
            # Normal specific query search
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

    # Accumulate ratings into session state
    if isinstance(feedback, RefineFeedback):
        for rating in feedback.ratings:
            idx = rating.get("index", 0)
            val = rating.get("value", "up")
            # Find the matching result to store title/snippet/url
            matched = next((r for r in state.last_results if r.index == idx), None)
            state.all_ratings.append(
                RatingRecord(
                    turn=state.refinement_turn,
                    index=idx,
                    value=val,
                    title=matched.title if matched else "",
                    snippet=matched.snippet if matched else "",
                    url=matched.url if matched else "",
                )
            )
        state.refinement_turn += 1

    # Extract preference patterns every 2nd turn or if 4+ new ratings
    preference_history: dict[str, Any] | None = None
    new_rating_count = len(feedback.ratings) if isinstance(feedback, RefineFeedback) else 0
    should_extract = (
        len(state.all_ratings) >= 3
        and (state.refinement_turn % 2 == 0 or new_rating_count >= 4)
    )
    if should_extract:
        liked, disliked = _extract_preference_patterns(state.all_ratings)
        state.liked_attributes = liked
        state.disliked_attributes = disliked

    if state.liked_attributes or state.disliked_attributes:
        preference_history = {
            "liked": state.liked_attributes,
            "disliked": state.disliked_attributes,
            "all_ratings_summary": f"{len(state.all_ratings)} total ratings across {state.refinement_turn} rounds",
        }

    feedback_meta = feedback.model_dump() if feedback else None
    updated, query, intro = refine_request(
        state.request,
        state.last_results,
        user_content,
        feedback_meta,
        preference_history=preference_history,
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


def get_session_response(session_id: str, *, user_id: str = "default") -> FindTurnResponse:
    row = get_session(session_id, user_id=user_id)
    if row is None:
        raise ValueError(f"Session not found: {session_id}")
    state = load_session_state(session_id, user_id=user_id)
    last_assistant = next(
        (m.content for m in reversed(list_messages(session_id)) if m.role == "assistant"),
        None,
    )
    return _turn_response(session_id, state, last_assistant)


def reset_session(session_id: str, *, user_id: str = "default") -> FindTurnResponse:
    row = get_session(session_id, user_id=user_id)
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
