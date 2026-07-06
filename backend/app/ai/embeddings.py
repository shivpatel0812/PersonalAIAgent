"""
Embeddings generation using OpenAI API for vector similarity search.
"""

from functools import lru_cache
from typing import List

from openai import OpenAI

from app.ai.config import get_ai_settings


@lru_cache(maxsize=1)
def get_embedding_client() -> OpenAI:
    """
    Get cached OpenAI client for embeddings generation.

    Returns:
        OpenAI client instance
    """
    settings = get_ai_settings()
    return OpenAI(api_key=settings.openai_api_key)


def prepare_text_for_embedding(question: str, answer: str | None = None) -> str:
    """
    Prepare text for embedding generation by combining question and answer.
    The question is repeated to give it more weight in the embedding.

    Args:
        question: The research question
        answer: The final answer (optional)

    Returns:
        Combined text optimized for embedding
    """
    # Repeat question to give it 2x weight in the embedding
    # This helps match on similar questions even if answers differ
    if answer:
        return f"{question}. {question}. {answer}"
    return f"{question}. {question}"


def generate_embedding(text: str) -> list[float] | None:
    """
    Generate embedding for a single text using OpenAI API.

    Args:
        text: Text to generate embedding for

    Returns:
        1536-dimensional embedding vector, or None if generation fails
    """
    try:
        settings = get_ai_settings()
        client = get_embedding_client()

        response = client.embeddings.create(
            model=settings.openai_embedding_model,
            input=text,
            encoding_format="float"
        )

        return response.data[0].embedding

    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None


def generate_embeddings_batch(texts: List[str]) -> List[list[float] | None]:
    """
    Generate embeddings for multiple texts in a single API call.
    More efficient than individual calls for migration scripts.

    Args:
        texts: List of texts to generate embeddings for

    Returns:
        List of embeddings (1536-dimensional vectors) or None for failed generations
    """
    try:
        settings = get_ai_settings()
        client = get_embedding_client()

        response = client.embeddings.create(
            model=settings.openai_embedding_model,
            input=texts,
            encoding_format="float"
        )

        # Sort by index to ensure correct order
        embeddings_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in embeddings_data]

    except Exception as e:
        print(f"Error generating batch embeddings: {e}")
        # Return None for each failed text
        return [None] * len(texts)
