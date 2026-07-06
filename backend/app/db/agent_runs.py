from datetime import datetime

from app.ai.agent.loop import AgentResult
from app.ai.config import get_ai_settings
from app.ai.embeddings import generate_embedding, prepare_text_for_embedding
from app.supabase_client import get_supabase_client


def _run_status(result: AgentResult) -> str:
    if result.steps and result.steps[-1].action == "answer":
        return "completed"
    return "failed"


def save_agent_run(result: AgentResult) -> str:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    status = _run_status(result)

    # Prepare data for insertion
    run_data = {
        "question": result.question,
        "status": status,
        "final_answer": result.answer,
    }

    # Generate embedding for completed runs
    settings = get_ai_settings()
    if status == "completed" and result.answer:
        text = prepare_text_for_embedding(result.question, result.answer)
        embedding = generate_embedding(text)

        if embedding:
            run_data["embedding"] = embedding
            run_data["embedding_model"] = settings.openai_embedding_model
            run_data["embedding_generated_at"] = datetime.utcnow().isoformat()

    run_response = (
        client.table("agent_runs")
        .insert(run_data)
        .execute()
    )

    if not run_response.data:
        raise ValueError("Failed to create agent run")

    run_id = run_response.data[0]["id"]

    if result.steps:
        step_rows = [
            {
                "run_id": run_id,
                "step_number": step.iteration,
                "step_type": step.action,
                "content": step.model_dump(),
            }
            for step in result.steps
        ]
        client.table("agent_steps").insert(step_rows).execute()

    return run_id


def list_agent_runs(limit: int = 20) -> list[dict]:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    response = (
        client.table("agent_runs")
        .select("id, question, status, final_answer, created_at, updated_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def get_agent_run(run_id: str) -> dict | None:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    run_response = (
        client.table("agent_runs")
        .select("id, question, status, final_answer, created_at, updated_at, embedding_model, embedding_generated_at")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )

    if not run_response.data:
        return None

    run = run_response.data[0]
    steps_response = (
        client.table("agent_steps")
        .select("id, step_number, step_type, content, created_at")
        .eq("run_id", run_id)
        .order("step_number")
        .execute()
    )
    run["steps"] = steps_response.data or []
    return run


def find_similar_runs_vector(
    query_embedding: list[float],
    match_threshold: float = 0.3,
    match_count: int = 3
) -> list[dict]:
    """
    Find similar agent runs using vector similarity search.

    Args:
        query_embedding: 1536-dimensional embedding vector for the query
        match_threshold: Minimum similarity score (0-1) to include in results
        match_count: Maximum number of results to return

    Returns:
        List of similar runs with similarity scores
    """
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    try:
        response = client.rpc(
            "find_similar_runs",
            {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": match_count,
            }
        ).execute()

        return response.data or []

    except Exception as e:
        print(f"Error in vector similarity search: {e}")
        return []
