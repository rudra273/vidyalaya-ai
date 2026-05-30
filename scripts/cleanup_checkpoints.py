"""Run checkpoint cleanup as a standalone job (Phase 7).

Intended for a scheduled task (e.g. Railway cron) or manual run:

    PYTHONPATH=src python scripts/cleanup_checkpoints.py
    PYTHONPATH=src python scripts/cleanup_checkpoints.py --keep 50 --idle-days 90

Reads DATABASE_URL from the environment like the app. Exits non-zero on error
so a scheduler can alert.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from vidyalaya_ai.db.engine import close_engine
from vidyalaya_ai.maintenance import run_checkpoint_cleanup


async def _main(keep: int, idle_days: int) -> int:
    try:
        result = await run_checkpoint_cleanup(
            keep_last_n=keep, idle_expire_days=idle_days
        )
    finally:
        await close_engine()
    print(
        f"deleted checkpoints={result.checkpoints_deleted} "
        f"writes={result.writes_deleted} blobs={result.blobs_deleted}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Prune LangGraph checkpoints.")
    parser.add_argument("--keep", type=int, default=50, help="Keep last N per thread.")
    parser.add_argument(
        "--idle-days", type=int, default=90, help="Expire threads idle > N days."
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.keep, args.idle_days)))


if __name__ == "__main__":
    main()
