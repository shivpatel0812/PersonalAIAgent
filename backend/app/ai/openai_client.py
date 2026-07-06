from functools import lru_cache

from openai import OpenAI

from app.ai.config import settings


@lru_cache
def get_openai_client() -> OpenAI | None:
    if not settings.openai_configured:
        return None

    return OpenAI(api_key=settings.openai_api_key)


def chat(message: str) -> str:
    return chat_messages([{"role": "user", "content": message}])


def chat_messages(messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
    client = get_openai_client()
    if client is None:
        raise ValueError("OpenAI API key is not configured")

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        max_tokens=max_tokens,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("OpenAI returned an empty response")

    return content
