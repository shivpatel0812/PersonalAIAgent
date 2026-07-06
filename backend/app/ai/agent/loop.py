import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.ai.agent.memory import PastRunMemory
from app.ai.config import settings
from app.ai.openai_client import chat_messages
from app.ai.tools.tavily import SearchResult
from app.ai.tools.tavily_extract import ExtractResult
from app.ai.tools.answer import AnswerResult
from app.ai.tools.registry import get_tool_registry, create_dynamic_system_prompt

MAX_ITERATIONS = 25


class AgentStep(BaseModel):
    iteration: int
    action: str  # Allow any tool action (e.g., "search", "scrape", "answer", "add_calendar_event", etc.)
    llm_response: str
    query: str | None = None
    url: str | None = None
    search_results: list[SearchResult] | None = None
    scraped_content: str | None = None
    scraped_title: str | None = None
    content_truncated: bool | None = None
    tool_result: dict[str, Any] | None = None  # For storing results from non-search/scrape tools


class AgentResult(BaseModel):
    question: str
    answer: str
    iterations: int
    steps: list[AgentStep] = Field(default_factory=list)
    memory_runs: list[PastRunMemory] = Field(default_factory=list)


def _format_conversation_context(
    conversation_history: list[dict[str, str]] | None,
    page_context: str | None,
) -> str:
    if not conversation_history and not page_context:
        return ""

    lines: list[str] = []

    if page_context:
        lines.append(page_context)

    if conversation_history:
        lines.append(
            "You are continuing an ongoing conversation in this thread. "
            "Use the prior messages as context. Search again only if you need "
            "new or updated information."
        )
        lines.append("")
        lines.append("Previous conversation:")
        for index, turn in enumerate(conversation_history, start=1):
            role_label = "User" if turn["role"] == "user" else "Assistant"
            lines.append(f"{index}. {role_label}: {turn['content']}")
            lines.append("")

    return "\n".join(lines).strip()


def _build_initial_messages(
    question: str,
    memory_context: str | None,
    conversation_history: list[dict[str, str]] | None = None,
    page_context: str | None = None,
) -> list[dict[str, str]]:
    # Generate system prompt dynamically from registered tools
    system_prompt = create_dynamic_system_prompt(context_query=question)
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    context_parts: list[str] = []
    if memory_context:
        context_parts.append(memory_context)

    conversation_context = _format_conversation_context(conversation_history, page_context)
    if conversation_context:
        context_parts.append(conversation_context)

    if context_parts:
        user_content = "\n\n".join(context_parts) + f"\n\nCurrent question:\n{question}"
    else:
        user_content = question

    messages.append({"role": "user", "content": user_content})
    return messages


def _parse_agent_decision(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    return json.loads(cleaned)


def _format_search_results(query: str, results: list[SearchResult]) -> str:
    if not results:
        return (
            f'Search results for "{query}":\nNo results found. Try a different query.'
        )

    lines = [f'Search results for "{query}":']
    for index, result in enumerate(results, start=1):
        lines.append(f"{index}. {result.title}")
        lines.append(f"   URL: {result.url}")
        lines.append(f"   Snippet: {result.snippet}")
    lines.append(
        "What do you want to do next? Scrape a URL for full content, search again, or answer."
    )
    return "\n".join(lines)


def _format_scraped_content(extract: ExtractResult) -> str:
    truncated_note = " (truncated)" if extract.truncated else ""
    return (
        f'Full page content from "{extract.url}":\n'
        f"Title: {extract.title}\n"
        f"Content{truncated_note}:\n"
        f"{extract.content}\n\n"
        "What do you want to do next? Scrape another URL, search again, or answer."
    )


def _invalid_json_step(iteration: int, llm_response: str) -> AgentStep:
    return AgentStep(iteration=iteration, action="error", llm_response=llm_response)


def _json_retry_message(available_actions: list[str]) -> str:
    actions_str = '", "'.join(available_actions)
    return (
        f'Your response was not valid JSON. Reply again using only the '
        f'required JSON format with action "{actions_str}".'
    )


def run_agent(
    question: str,
    max_iterations: int = MAX_ITERATIONS,
    memory_context: str | None = None,
    memory_runs: list[PastRunMemory] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    page_context: str | None = None,
) -> AgentResult:
    if not settings.openai_configured:
        raise ValueError("OpenAI API key is not configured")
    if not settings.tavily_configured:
        raise ValueError("Tavily API key is not configured")

    max_iterations = max(1, min(max_iterations, MAX_ITERATIONS))

    # Get the tool registry
    registry = get_tool_registry(context_query=question)
    available_actions = registry.get_available_actions()

    messages = _build_initial_messages(
        question,
        memory_context,
        conversation_history=conversation_history,
        page_context=page_context,
    )
    steps: list[AgentStep] = []
    recalled = memory_runs or []

    print(f"\n=== Agent started ===")
    print(f"Question: {question}")
    if recalled:
        print(f"Memory: {len(recalled)} related past run(s) injected\n")
    else:
        print()

    for iteration in range(1, max_iterations + 1):
        print(f"--- Iteration {iteration} ---")

        llm_response = chat_messages(messages)
        print(f"LLM decision: {llm_response}\n")

        try:
            decision = _parse_agent_decision(llm_response)
        except json.JSONDecodeError:
            print("Failed to parse LLM JSON response. Asking model to retry.\n")
            steps.append(_invalid_json_step(iteration, llm_response))
            messages.append({"role": "assistant", "content": llm_response})
            messages.append({"role": "user", "content": _json_retry_message(available_actions)})
            continue

        action = decision.get("action")

        # Look up the tool in the registry
        tool = registry.get(action) if action else None

        if not tool:
            messages.append({"role": "assistant", "content": llm_response})
            actions_str = '", "'.join(available_actions)
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f'Unknown action "{action}". Use only "{actions_str}" in JSON format.'
                    ),
                }
            )
            continue

        # Validate parameters
        is_valid, error_msg = tool.validate_parameters(decision)
        if not is_valid:
            messages.append({"role": "assistant", "content": llm_response})
            messages.append(
                {
                    "role": "user",
                    "content": f"{error_msg}. Please try again.",
                }
            )
            continue

        # Execute the tool
        try:
            print(f"Executing tool: {tool.name}")
            result = tool.execute(**decision)
        except Exception as exc:
            print(f"Tool execution failed: {exc}\n")
            messages.append({"role": "assistant", "content": llm_response})
            messages.append(
                {
                    "role": "user",
                    "content": f"Tool execution failed: {exc}. Please try again.",
                }
            )
            continue

        # Handle special case: answer tool ends the loop
        if action == "answer" and isinstance(result, AnswerResult):
            steps.append(
                AgentStep(
                    iteration=iteration,
                    action="answer",
                    llm_response=llm_response,
                )
            )
            print(f"=== Agent finished in {iteration} iteration(s) ===\n")
            return AgentResult(
                question=question,
                answer=result.response,
                iterations=iteration,
                steps=steps,
                memory_runs=recalled,
            )

        # Handle search tool
        if action == "search" and isinstance(result, list):
            query = decision.get("query", "")
            print(f"Tavily returned {len(result)} result(s)")
            for index, search_result in enumerate(result, start=1):
                print(f"  {index}. {search_result.title} ({search_result.url})")
            print()

            steps.append(
                AgentStep(
                    iteration=iteration,
                    action="search",
                    llm_response=llm_response,
                    query=query,
                    search_results=result,
                )
            )

            messages.append({"role": "assistant", "content": llm_response})
            messages.append(
                {"role": "user", "content": _format_search_results(query, result)}
            )
            continue

        # Handle scrape tool
        if action == "scrape" and isinstance(result, ExtractResult):
            print(f"Extracted {len(result.content)} characters from {result.url}\n")

            steps.append(
                AgentStep(
                    iteration=iteration,
                    action="scrape",
                    llm_response=llm_response,
                    url=result.url,
                    scraped_title=result.title,
                    scraped_content=result.content,
                    content_truncated=result.truncated,
                )
            )

            messages.append({"role": "assistant", "content": llm_response})
            messages.append(
                {"role": "user", "content": _format_scraped_content(result)}
            )
            continue

        # Handle other tools (calendar, etc.)
        # Result should be a Pydantic model with model_dump()
        if hasattr(result, 'model_dump'):
            result_dict = result.model_dump()
            print(f"Tool {action} completed: {result_dict}\n")

            steps.append(
                AgentStep(
                    iteration=iteration,
                    action=action,
                    llm_response=llm_response,
                    tool_result=result_dict,
                )
            )

            messages.append({"role": "assistant", "content": llm_response})
            # Format the tool result as feedback to the agent
            feedback = f"Tool '{action}' executed successfully. Result:\n{json.dumps(result_dict, indent=2)}\n\nWhat do you want to do next? You can use another tool or provide an answer."
            messages.append({"role": "user", "content": feedback})
            continue

    print(f"=== Agent hit max iterations ({max_iterations}) ===\n")
    return AgentResult(
        question=question,
        answer="The agent could not finish within the iteration limit. Try a simpler question.",
        iterations=max_iterations,
        steps=steps,
        memory_runs=recalled,
    )


def run_agent_streaming(
    question: str,
    max_iterations: int = MAX_ITERATIONS,
    memory_context: str | None = None,
    memory_runs: list[PastRunMemory] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    page_context: str | None = None,
):
    """
    Streaming version of run_agent that yields events as the agent runs.
    Yields dict events with type: "step", "complete", or "error".
    """
    if not settings.openai_configured:
        yield {"type": "error", "error": "OpenAI API key is not configured"}
        return
    if not settings.tavily_configured:
        yield {"type": "error", "error": "Tavily API key is not configured"}
        return

    max_iterations = max(1, min(max_iterations, MAX_ITERATIONS))

    # Get the tool registry
    registry = get_tool_registry(context_query=question)
    available_actions = registry.get_available_actions()

    messages = _build_initial_messages(
        question,
        memory_context,
        conversation_history=conversation_history,
        page_context=page_context,
    )
    steps: list[AgentStep] = []
    recalled = memory_runs or []

    if recalled:
        yield {
            "type": "memory",
            "runs": [run.model_dump() for run in recalled],
        }

    try:
        for iteration in range(1, max_iterations + 1):
            llm_response = chat_messages(messages)

            try:
                decision = _parse_agent_decision(llm_response)
            except json.JSONDecodeError:
                error_step = _invalid_json_step(iteration, llm_response)
                steps.append(error_step)
                yield {"type": "step", "step": error_step.model_dump()}

                messages.append({"role": "assistant", "content": llm_response})
                messages.append({"role": "user", "content": _json_retry_message(available_actions)})
                continue

            action = decision.get("action")

            # Look up the tool in the registry
            tool = registry.get(action) if action else None

            if not tool:
                messages.append({"role": "assistant", "content": llm_response})
                actions_str = '", "'.join(available_actions)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f'Unknown action "{action}". Use only "{actions_str}" in JSON format.'
                        ),
                    }
                )
                continue

            # Validate parameters
            is_valid, error_msg = tool.validate_parameters(decision)
            if not is_valid:
                messages.append({"role": "assistant", "content": llm_response})
                messages.append(
                    {
                        "role": "user",
                        "content": f"{error_msg}. Please try again.",
                    }
                )
                continue

            # Execute the tool
            try:
                result = tool.execute(**decision)
            except Exception as exc:
                messages.append({"role": "assistant", "content": llm_response})
                messages.append(
                    {
                        "role": "user",
                        "content": f"Tool execution failed: {exc}. Please try again.",
                    }
                )
                continue

            # Handle special case: answer tool ends the loop
            if action == "answer" and isinstance(result, AnswerResult):
                answer_step = AgentStep(
                    iteration=iteration,
                    action="answer",
                    llm_response=llm_response,
                )
                steps.append(answer_step)
                yield {"type": "step", "step": answer_step.model_dump()}

                yield {
                    "type": "complete",
                    "question": question,
                    "answer": result.response,
                    "iterations": iteration,
                    "steps": [s.model_dump() for s in steps],
                    "memory_runs": [run.model_dump() for run in recalled],
                }
                return

            # Handle search tool
            if action == "search" and isinstance(result, list):
                query = decision.get("query", "")

                search_step = AgentStep(
                    iteration=iteration,
                    action="search",
                    llm_response=llm_response,
                    query=query,
                    search_results=result,
                )
                steps.append(search_step)
                yield {"type": "step", "step": search_step.model_dump()}

                messages.append({"role": "assistant", "content": llm_response})
                messages.append(
                    {"role": "user", "content": _format_search_results(query, result)}
                )
                continue

            # Handle scrape tool
            if action == "scrape" and isinstance(result, ExtractResult):
                scrape_step = AgentStep(
                    iteration=iteration,
                    action="scrape",
                    llm_response=llm_response,
                    url=result.url,
                    scraped_title=result.title,
                    scraped_content=result.content,
                    content_truncated=result.truncated,
                )
                steps.append(scrape_step)
                yield {"type": "step", "step": scrape_step.model_dump()}

                messages.append({"role": "assistant", "content": llm_response})
                messages.append(
                    {"role": "user", "content": _format_scraped_content(result)}
                )
                continue

            # Handle other tools (calendar, etc.)
            if hasattr(result, 'model_dump'):
                result_dict = result.model_dump()

                tool_step = AgentStep(
                    iteration=iteration,
                    action=action,
                    llm_response=llm_response,
                    tool_result=result_dict,
                )
                steps.append(tool_step)
                yield {"type": "step", "step": tool_step.model_dump()}

                messages.append({"role": "assistant", "content": llm_response})
                feedback = f"Tool '{action}' executed successfully. Result:\n{json.dumps(result_dict, indent=2)}\n\nWhat do you want to do next? You can use another tool or provide an answer."
                messages.append({"role": "user", "content": feedback})
                continue

        yield {
            "type": "complete",
            "question": question,
            "answer": "The agent could not finish within the iteration limit. Try a simpler question.",
            "iterations": max_iterations,
            "steps": [s.model_dump() for s in steps],
            "memory_runs": [run.model_dump() for run in recalled],
        }

    except Exception as e:
        yield {"type": "error", "error": str(e)}
