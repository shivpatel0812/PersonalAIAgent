"""
Example calculator tool - demonstrates how to add a new tool to the registry.

This is a simple example showing the minimal code needed to create a custom tool.
To activate this tool, add it to the registry in registry.py:

    from app.ai.tools.calculator_example import CalculatorTool
    registry.register(CalculatorTool())
"""

from typing import Any
from pydantic import BaseModel
from app.ai.tools.base import Tool, ToolParameter


class CalculatorResult(BaseModel):
    """Result of a calculation."""
    expression: str
    result: float


class CalculatorTool(Tool):
    """Tool for performing basic arithmetic calculations."""

    @property
    def name(self) -> str:
        return "calculate"

    @property
    def description(self) -> str:
        return "evaluates a mathematical expression (supports +, -, *, /, parentheses)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "expression",
                "type": "string",
                "description": "the mathematical expression to evaluate (e.g., '2 + 2', '(5 * 3) - 1')",
                "required": True,
            }
        ]

    def execute(self, **kwargs) -> CalculatorResult:
        expression = kwargs.get("expression", "").strip()

        if not expression:
            raise ValueError("Expression parameter is required")

        # Simple evaluation (in production, use a proper math parser for security)
        # This is just for demonstration purposes
        try:
            # Only allow safe characters
            allowed_chars = set("0123456789+-*/() .")
            if not all(c in allowed_chars for c in expression):
                raise ValueError("Expression contains invalid characters")

            result = eval(expression, {"__builtins__": {}}, {})

            return CalculatorResult(
                expression=expression,
                result=float(result)
            )
        except Exception as e:
            raise ValueError(f"Failed to evaluate expression: {e}")


# Example usage (not executed unless imported and registered):
if __name__ == "__main__":
    calc = CalculatorTool()

    # Test the tool
    result = calc.execute(expression="(10 + 5) * 2")
    print(f"{result.expression} = {result.result}")  # (10 + 5) * 2 = 30.0

    # Show JSON format
    import json
    print("\nJSON format for LLM:")
    print(json.dumps(calc.get_json_example(), indent=2))
