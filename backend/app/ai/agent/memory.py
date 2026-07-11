import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "what", "how", "why",
    "when", "where", "who", "which", "do", "does", "did", "can", "could",
    "would", "should", "will", "about", "for", "with", "from", "this",
    "that", "these", "those", "and", "or", "but", "in", "on", "at", "to",
    "of", "by", "as", "it", "its", "be", "been", "being", "have", "has",
    "had", "me", "my", "your", "you", "i", "we", "they", "their", "there",
    "any", "all", "some", "than", "then", "into", "also", "just", "not",
}

ANSWER_PREVIEW_CHARS = 600
MAX_MEMORY_RUNS = 3
CANDIDATE_RUN_LIMIT = 50
MIN_RELEVANCE_SCORE = 0.2


class PastRunMemory(BaseModel):
    id: str
    question: str
    answer_preview: str
    created_at: str
    relevance_score: float
    search_method: Literal["vector", "keyword"] = "keyword"


def extract_keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {word for word in words if len(word) >= 3 and word not in STOP_WORDS}


def _score_run_relevance(question: str, run: dict) -> float:
    query_keywords = extract_keywords(question)
    if not query_keywords:
        return 0.0

    run_question = run.get("question", "")
    run_answer = run.get("final_answer") or ""
    run_keywords = extract_keywords(f"{run_question} {run_answer}")

    overlap = query_keywords & run_keywords
    if not overlap:
        return 0.0

    score = len(overlap) / len(query_keywords)
    if extract_keywords(run_question) & query_keywords:
        score += 0.25
    return round(score, 3)


def _truncate_answer(answer: str, max_chars: int = ANSWER_PREVIEW_CHARS) -> str:
    cleaned = " ".join(answer.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _find_related_runs_keyword(
    question: str,
    limit: int = MAX_MEMORY_RUNS,
    min_score: float = MIN_RELEVANCE_SCORE,
    *,
    user_id: str = "default",
) -> list[PastRunMemory]:
    """
    Find related runs using keyword-based matching (fallback method).

    Args:
        question: The research question
        limit: Maximum number of runs to return
        min_score: Minimum relevance score (0-1)
        user_id: Authenticated user whose past runs to search

    Returns:
        List of related runs with relevance scores
    """
    from app.db.agent_runs import list_agent_runs

    try:
        candidates = list_agent_runs(limit=CANDIDATE_RUN_LIMIT, user_id=user_id)
    except Exception as exc:
        print(f"Failed to load past runs for memory: {exc}")
        return []

    scored: list[tuple[float, dict]] = []
    for run in candidates:
        if run.get("status") != "completed":
            continue
        if not run.get("final_answer"):
            continue

        score = _score_run_relevance(question, run)
        if score >= min_score:
            scored.append((score, run))

    scored.sort(key=lambda item: (item[0], item[1].get("created_at", "")), reverse=True)

    memory_runs: list[PastRunMemory] = []
    for score, run in scored[:limit]:
        memory_runs.append(
            PastRunMemory(
                id=run["id"],
                question=run["question"],
                answer_preview=_truncate_answer(run["final_answer"]),
                created_at=run.get("created_at", ""),
                relevance_score=score,
                search_method="keyword",
            )
        )

    return memory_runs


def find_related_runs(
    question: str,
    limit: int = MAX_MEMORY_RUNS,
    min_score: float = MIN_RELEVANCE_SCORE,
    *,
    user_id: str = "default",
) -> list[PastRunMemory]:
    """
    Find related runs using vector similarity search with automatic fallback to keyword matching.

    Args:
        question: The research question
        limit: Maximum number of runs to return
        min_score: Minimum relevance score (0-1)
        user_id: Authenticated user whose past runs to search

    Returns:
        List of related runs with relevance scores
    """
    from app.ai.config import get_ai_settings
    from app.ai.embeddings import generate_embedding, prepare_text_for_embedding
    from app.db.agent_runs import claim_legacy_default_runs, find_similar_runs_vector

    claim_legacy_default_runs(user_id)
    settings = get_ai_settings()

    # Try vector similarity search if enabled
    if settings.enable_vector_search:
        try:
            # Generate embedding for the question
            text = prepare_text_for_embedding(question)
            query_embedding = generate_embedding(text)

            if query_embedding:
                # Perform vector similarity search
                similar_runs = find_similar_runs_vector(
                    query_embedding=query_embedding,
                    match_threshold=min_score,
                    match_count=limit,
                    user_id=user_id,
                )

                if similar_runs:
                    # Convert to PastRunMemory format
                    memory_runs: list[PastRunMemory] = []
                    for run in similar_runs:
                        memory_runs.append(
                            PastRunMemory(
                                id=run["id"],
                                question=run["question"],
                                answer_preview=_truncate_answer(run["final_answer"]),
                                created_at=run.get("created_at", ""),
                                relevance_score=round(run["similarity"], 3),
                                search_method="vector",
                            )
                        )
                    return memory_runs

        except Exception as e:
            print(f"Vector search failed, falling back to keyword matching: {e}")

    # Fall back to keyword-based matching
    return _find_related_runs_keyword(question, limit, min_score, user_id=user_id)


def format_memory_context(memory_runs: list[PastRunMemory]) -> str:
    if not memory_runs:
        return ""

    lines = [
        "You have researched related topics before. Use this prior knowledge to inform your approach.",
        "Verify anything important with fresh search/scrape if the topic may have changed.",
        "",
        "Past research sessions:",
    ]

    for index, run in enumerate(memory_runs, start=1):
        date_label = _format_date(run.created_at)
        lines.append(f"{index}. [{date_label}] Question: {run.question}")
        lines.append(f"   Prior answer: {run.answer_preview}")
        lines.append("")

    return "\n".join(lines).strip()


def _format_date(created_at: str) -> str:
    if not created_at:
        return "unknown date"
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return parsed.strftime("%b %d, %Y")
    except ValueError:
        return created_at[:10]
