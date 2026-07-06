from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx
import json

from app.ai.config import settings
from app.ai.agent.loop import AgentStep, run_agent, run_agent_streaming
from app.ai.agent.memory import PastRunMemory, find_related_runs, format_memory_context
from app.ai.openai_client import chat
from app.ai.tools.tavily import SearchResult, web_search
from app.db.agent_runs import get_agent_run, list_agent_runs, save_agent_run
from app.db.conversation_threads import (
    PAGE_CONTEXT,
    VALID_PAGE_TYPES,
    append_conversation_turn,
    format_history_for_agent,
    get_conversation,
    get_or_create_thread,
    validate_page_type,
)

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str = Field(
        default="Reply with exactly: OpenAI connection works.",
        min_length=1,
        max_length=4000,
    )


class ChatResponse(BaseModel):
    message: str
    model: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=10)


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class ResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    max_iterations: int = Field(default=5, ge=1, le=25)
    page_type: str | None = Field(default=None, max_length=32)


class ResearchResponse(BaseModel):
    run_id: str | None = None
    question: str
    answer: str
    iterations: int
    steps: list[AgentStep]
    saved: bool = False
    memory_runs: list[PastRunMemory] = Field(default_factory=list)


def _load_research_memory(question: str) -> tuple[str | None, list[PastRunMemory]]:
    memory_runs = find_related_runs(question)
    if not memory_runs:
        return None, []
    return format_memory_context(memory_runs), memory_runs


def _load_conversation_context(page_type: str | None) -> tuple[
    list[dict[str, str]] | None, str | None, str | None
]:
    if not page_type:
        return None, None, None

    try:
        page_type = validate_page_type(page_type)
        thread = get_or_create_thread(page_type)
        messages = get_conversation(page_type)["messages"]
        history = format_history_for_agent(messages)
        return history, PAGE_CONTEXT[page_type], thread["id"]
    except Exception as exc:
        print(f"Failed to load conversation context: {exc}")
        try:
            page_type = validate_page_type(page_type)
            return None, PAGE_CONTEXT[page_type], None
        except ValueError:
            return None, None, None


class AgentRunSummary(BaseModel):
    id: str
    question: str
    status: str
    final_answer: str | None
    created_at: str
    updated_at: str


class AgentRunDetail(AgentRunSummary):
    steps: list[dict]


class ConversationMessage(BaseModel):
    id: str
    role: str
    content: str
    steps: list[dict] = Field(default_factory=list)
    run_id: str | None = None
    source: str = "user"
    created_at: str


class ConversationResponse(BaseModel):
    thread_id: str
    page_type: str
    title: str
    updated_at: str
    messages: list[ConversationMessage]


@router.post("/chat", response_model=ChatResponse)
def ai_chat(body: ChatRequest) -> ChatResponse:
    if not settings.openai_configured:
        raise HTTPException(status_code=503, detail="OpenAI API key is not configured")

    try:
        reply = chat(body.message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {exc}") from exc

    return ChatResponse(message=reply, model=settings.openai_model)


@router.post("/search", response_model=SearchResponse)
def ai_search(body: SearchRequest) -> SearchResponse:
    if not settings.tavily_configured:
        raise HTTPException(status_code=503, detail="Tavily API key is not configured")

    try:
        results = web_search(body.query, max_results=body.max_results)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Tavily request failed: {exc.response.text}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Tavily request failed: {exc}") from exc

    return SearchResponse(query=body.query, results=results)


@router.post("/research", response_model=ResearchResponse)
def ai_research(body: ResearchRequest) -> ResearchResponse:
    if not settings.openai_configured:
        raise HTTPException(status_code=503, detail="OpenAI API key is not configured")
    if not settings.tavily_configured:
        raise HTTPException(status_code=503, detail="Tavily API key is not configured")

    memory_context, memory_runs = _load_research_memory(body.question)
    conversation_history, page_context, thread_id = _load_conversation_context(body.page_type)

    try:
        result = run_agent(
            body.question,
            max_iterations=body.max_iterations,
            memory_context=memory_context,
            memory_runs=memory_runs,
            conversation_history=conversation_history,
            page_context=page_context,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent failed: {exc}") from exc

    run_id: str | None = None
    saved = False
    try:
        run_id = save_agent_run(result)
        saved = True
        if thread_id:
            append_conversation_turn(
                thread_id=thread_id,
                user_content=body.question,
                assistant_content=result.answer,
                steps=result.steps,
                run_id=run_id,
            )
    except Exception as exc:
        print(f"Failed to save agent run to Supabase: {exc}")

    return ResearchResponse(
        run_id=run_id,
        question=result.question,
        answer=result.answer,
        iterations=result.iterations,
        steps=result.steps,
        saved=saved,
        memory_runs=result.memory_runs,
    )


@router.post("/research/stream")
def ai_research_stream(body: ResearchRequest):
    """
    Streaming version of /research that returns Server-Sent Events (SSE).
    Each event contains: event: <type>\ndata: <json>\n\n
    Event types: step, complete, error
    """
    if not settings.openai_configured:
        raise HTTPException(status_code=503, detail="OpenAI API key is not configured")
    if not settings.tavily_configured:
        raise HTTPException(status_code=503, detail="Tavily API key is not configured")

    memory_context, memory_runs = _load_research_memory(body.question)
    conversation_history, page_context, thread_id = _load_conversation_context(body.page_type)

    def event_generator():
        try:
            for event in run_agent_streaming(
                body.question,
                max_iterations=body.max_iterations,
                memory_context=memory_context,
                memory_runs=memory_runs,
                conversation_history=conversation_history,
                page_context=page_context,
            ):
                event_type = event.get("type", "unknown")
                event_data = json.dumps(event)
                yield f"event: {event_type}\ndata: {event_data}\n\n"

                # If complete, try to save to database
                if event_type == "complete":
                    try:
                        from app.ai.agent.loop import AgentResult
                        result = AgentResult(
                            question=event["question"],
                            answer=event["answer"],
                            iterations=event["iterations"],
                            steps=[AgentStep(**s) for s in event["steps"]],
                            memory_runs=[
                                PastRunMemory(**run)
                                for run in event.get("memory_runs", [])
                            ],
                        )
                        run_id = save_agent_run(result)
                        if thread_id:
                            try:
                                append_conversation_turn(
                                    thread_id=thread_id,
                                    user_content=body.question,
                                    assistant_content=result.answer,
                                    steps=result.steps,
                                    run_id=run_id,
                                )
                            except Exception as conv_exc:
                                print(f"Failed to save conversation turn: {conv_exc}")
                        # Send additional event with run_id
                        saved_event = {"type": "saved", "run_id": run_id}
                        yield f"event: saved\ndata: {json.dumps(saved_event)}\n\n"
                    except Exception as exc:
                        print(f"Failed to save agent run to Supabase: {exc}")

        except Exception as exc:
            error_event = {"type": "error", "error": str(exc)}
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{page_type}", response_model=ConversationResponse)
def ai_get_conversation(page_type: str) -> ConversationResponse:
    if page_type not in VALID_PAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid page_type: {page_type}")

    try:
        conversation = get_conversation(page_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load conversation: {exc}") from exc

    return ConversationResponse(
        thread_id=conversation["thread_id"],
        page_type=conversation["page_type"],
        title=conversation["title"],
        updated_at=conversation["updated_at"],
        messages=[ConversationMessage(**message) for message in conversation["messages"]],
    )


@router.get("/runs", response_model=list[AgentRunSummary])
def ai_list_runs(limit: int = 20) -> list[AgentRunSummary]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")

    try:
        runs = list_agent_runs(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load runs: {exc}") from exc

    return [AgentRunSummary(**run) for run in runs]


@router.get("/runs/{run_id}", response_model=AgentRunDetail)
def ai_get_run(run_id: str) -> AgentRunDetail:
    try:
        run = get_agent_run(run_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load run: {exc}") from exc

    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = run.pop("steps", [])
    return AgentRunDetail(**run, steps=steps)
