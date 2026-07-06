# Adding New Tools to the Agent

The tool registry system makes it easy to add new capabilities to the agent without modifying core logic.

## Quick Start: Adding a New Tool

### Step 1: Create Your Tool Class

Create a new file in `app/ai/tools/` (e.g., `my_tool.py`):

```python
from typing import Any
from pydantic import BaseModel
from app.ai.tools.base import Tool, ToolParameter


class MyToolResult(BaseModel):
    """Result model for your tool."""
    output: str


class MyTool(Tool):
    """Your custom tool description."""

    @property
    def name(self) -> str:
        return "my_action"  # This is what the LLM uses in JSON

    @property
    def description(self) -> str:
        return "describes what this tool does"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "input",
                "type": "string",
                "description": "what the input parameter means",
                "required": True,
            }
        ]

    def execute(self, **kwargs) -> MyToolResult:
        input_value = kwargs.get("input", "")
        # Your tool logic here
        result = f"Processed: {input_value}"
        return MyToolResult(output=result)
```

### Step 2: Register Your Tool

Edit `app/ai/tools/registry.py` and add your tool:

```python
from app.ai.tools.my_tool import MyTool  # Add import

def get_tool_registry(context_query: str | None = None) -> ToolRegistry:
    registry = ToolRegistry()

    # Existing tools
    registry.register(WebSearchTool())
    registry.register(ExtractUrlTool(context_query=context_query))
    registry.register(AnswerTool())

    # Add your new tool
    registry.register(MyTool())

    return registry
```

### Step 3: Update Agent Steps (Optional)

If you want to track your tool's results in the agent steps, update `AgentStep` in `loop.py`:

```python
class AgentStep(BaseModel):
    iteration: int
    action: Literal["search", "scrape", "answer", "my_action", "error"]
    # ... existing fields ...
    my_tool_output: str | None = None  # Add your result field
```

Then add handling in `run_agent()` and `run_agent_streaming()`:

```python
# After tool execution
if action == "my_action" and isinstance(result, MyToolResult):
    steps.append(
        AgentStep(
            iteration=iteration,
            action="my_action",
            llm_response=llm_response,
            my_tool_output=result.output,
        )
    )

    messages.append({"role": "assistant", "content": llm_response})
    messages.append(
        {"role": "user", "content": f"Tool result: {result.output}"}
    )
    continue
```

### That's It!

Your tool is now available to the agent. The system prompt will automatically include:
- Tool description
- Parameter schema
- JSON format example

## Architecture Overview

```
Tool Base Class (base.py)
    ↓
Concrete Tools (tavily.py, answer.py, my_tool.py, ...)
    ↓
Tool Registry (registry.py)
    ↓
Agent Loop (loop.py) - looks up and executes tools dynamically
```

## Key Benefits

1. **No hardcoded if/elif** - Tools are looked up dynamically by name
2. **Self-documenting** - System prompt generated automatically from tool metadata
3. **Type-safe** - Pydantic models ensure correct data flow
4. **Easy to extend** - Just create a class and register it
5. **Validation built-in** - Parameters are validated before execution

## Example: Calculator Tool

See `calculator_example.py` for a complete example of a simple calculator tool.

## Advanced: Tools with Context

Some tools need context from the current session (like `ExtractUrlTool` uses the question):

```python
class ContextAwareTool(Tool):
    def __init__(self, session_data: dict):
        self._session_data = session_data

    # ... rest of implementation
```

Register with context in `registry.py`:

```python
registry.register(ContextAwareTool(session_data=some_data))
```

## Troubleshooting

**Tool not being called by LLM:**
- Check that the tool name is registered correctly
- Verify the description clearly explains when to use it
- Ensure parameters are well-documented

**Validation errors:**
- Make sure required parameters have `"required": True`
- Check parameter names match between Tool definition and execute()

**Runtime errors:**
- Add proper error handling in execute()
- Return descriptive error messages to guide the LLM
