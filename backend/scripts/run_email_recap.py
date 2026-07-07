#!/usr/bin/env python3
"""Manually run the email recap agent from the command line."""

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running as: python scripts/run_email_recap.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.email_recap.job import run_email_recap


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the email recap agent")
    parser.add_argument(
        "--slot",
        choices=["morning", "evening"],
        default="morning",
        help="Recap time slot (affects lookback window and subject)",
    )
    args = parser.parse_args()

    result = asyncio.run(run_email_recap(slot=args.slot))
    print(result)

    if result.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
