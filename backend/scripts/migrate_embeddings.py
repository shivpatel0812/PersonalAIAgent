"""
Migration script to generate embeddings for existing agent runs.

Usage:
    # Preview what would be processed
    python -m scripts.migrate_embeddings --dry-run

    # Run migration with custom batch size
    python -m scripts.migrate_embeddings --batch-size=50

    # Process only a specific number of runs
    python -m scripts.migrate_embeddings --limit=100
"""

import argparse
import time
from datetime import datetime

from app.ai.config import get_ai_settings
from app.ai.embeddings import generate_embeddings_batch, prepare_text_for_embedding
from app.supabase_client import get_supabase_client


def get_runs_without_embeddings(limit: int | None = None) -> list[dict]:
    """
    Fetch agent runs that don't have embeddings yet.

    Args:
        limit: Maximum number of runs to fetch (None for all)

    Returns:
        List of runs without embeddings
    """
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    query = (
        client.table("agent_runs")
        .select("id, question, final_answer, created_at")
        .eq("status", "completed")
        .is_("embedding", "null")
        .not_.is_("final_answer", "null")
        .order("created_at", desc=False)  # Process oldest first
    )

    if limit:
        query = query.limit(limit)

    response = query.execute()
    return response.data or []


def update_run_embedding(run_id: str, embedding: list[float]) -> bool:
    """
    Update a single run with its embedding.

    Args:
        run_id: ID of the run to update
        embedding: 1536-dimensional embedding vector

    Returns:
        True if update succeeded, False otherwise
    """
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    settings = get_ai_settings()

    try:
        client.table("agent_runs").update({
            "embedding": embedding,
            "embedding_model": settings.openai_embedding_model,
            "embedding_generated_at": datetime.utcnow().isoformat(),
        }).eq("id", run_id).execute()
        return True
    except Exception as e:
        print(f"  ERROR: Failed to update run {run_id}: {e}")
        return False


def migrate_embeddings(
    batch_size: int = 50,
    dry_run: bool = False,
    limit: int | None = None,
    delay_seconds: float = 1.0,
):
    """
    Generate and store embeddings for all agent runs that don't have them.

    Args:
        batch_size: Number of runs to process per API call
        dry_run: If True, only preview what would be done
        limit: Maximum total runs to process (None for all)
        delay_seconds: Delay between batches to avoid rate limits
    """
    print("=" * 60)
    print("EMBEDDINGS MIGRATION SCRIPT")
    print("=" * 60)

    if dry_run:
        print("\nDRY RUN MODE - No changes will be made\n")

    # Fetch runs without embeddings
    print(f"Fetching runs without embeddings...")
    runs = get_runs_without_embeddings(limit=limit)

    if not runs:
        print("✓ No runs need embeddings. All done!")
        return

    print(f"\nFound {len(runs)} runs without embeddings")

    if dry_run:
        print("\nWould process the following runs:")
        for i, run in enumerate(runs[:10], 1):  # Show first 10
            created = run.get("created_at", "unknown")[:10]
            question = run["question"][:60] + "..." if len(run["question"]) > 60 else run["question"]
            print(f"  {i}. [{created}] {question}")
        if len(runs) > 10:
            print(f"  ... and {len(runs) - 10} more")
        print(f"\nTotal batches: {(len(runs) + batch_size - 1) // batch_size}")
        return

    # Process in batches
    total_processed = 0
    total_succeeded = 0
    total_failed = 0
    total_batches = (len(runs) + batch_size - 1) // batch_size

    print(f"\nProcessing {len(runs)} runs in {total_batches} batches of {batch_size}...\n")

    for batch_num in range(0, len(runs), batch_size):
        batch = runs[batch_num:batch_num + batch_size]
        batch_index = (batch_num // batch_size) + 1

        print(f"Batch {batch_index}/{total_batches} ({len(batch)} runs)...")

        # Prepare texts for embedding
        texts = [
            prepare_text_for_embedding(run["question"], run["final_answer"])
            for run in batch
        ]

        # Generate embeddings
        print(f"  Generating embeddings...")
        embeddings = generate_embeddings_batch(texts)

        # Update database
        print(f"  Updating database...")
        for run, embedding in zip(batch, embeddings):
            if embedding is None:
                print(f"  WARNING: Failed to generate embedding for run {run['id']}")
                total_failed += 1
                continue

            if update_run_embedding(run["id"], embedding):
                total_succeeded += 1
            else:
                total_failed += 1

            total_processed += 1

        # Show progress
        success_rate = (total_succeeded / total_processed * 100) if total_processed > 0 else 0
        print(f"  Progress: {total_processed}/{len(runs)} processed, "
              f"{total_succeeded} succeeded, {total_failed} failed ({success_rate:.1f}% success)\n")

        # Rate limiting delay (except for last batch)
        if batch_index < total_batches:
            time.sleep(delay_seconds)

    # Final summary
    print("=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Total runs processed: {total_processed}")
    print(f"Successfully updated: {total_succeeded}")
    print(f"Failed: {total_failed}")
    if total_processed > 0:
        print(f"Success rate: {total_succeeded / total_processed * 100:.1f}%")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Generate embeddings for existing agent runs"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of runs to process per API call (default: 50)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be done without making changes"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of runs to process (default: all)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between batches (default: 1.0)"
    )

    args = parser.parse_args()

    try:
        migrate_embeddings(
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            limit=args.limit,
            delay_seconds=args.delay,
        )
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user. Safe to resume later.")
    except Exception as e:
        print(f"\n\nERROR: Migration failed: {e}")
        raise


if __name__ == "__main__":
    main()
