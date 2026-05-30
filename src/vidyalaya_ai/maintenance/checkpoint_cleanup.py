"""Checkpoint cleanup (Phase 7).

The LangGraph ``AsyncPostgresSaver`` keeps every checkpoint of every thread in
``checkpoints`` (+ ``checkpoint_writes`` / ``checkpoint_blobs``), which grows
unbounded. The model only ever needs the most recent few, and the permanent,
display-only history lives in our own ``messages`` table — so checkpoints are
safe to prune aggressively.

Two passes, both decoupled from the checkpointer's own connection pool (they run
their own SQL through the app's SQLAlchemy session):

1. **Keep last N per thread** — within each ``(thread_id, checkpoint_ns)``,
   rank rows by ``checkpoint_id`` (monotonic, time-sortable) and delete all but
   the newest N from ``checkpoints``.
2. **Expire idle threads** — the checkpoint tables have no ``created_at``; we
   derive last activity from ``messages.created_at`` (same thread_id). A thread
   whose newest message is older than the cutoff has *all* its checkpoints
   deleted. Threads with no messages at all are left to pass 1.

``checkpoint_writes`` and ``checkpoint_blobs`` are then swept of any rows whose
parent checkpoint no longer exists in ``checkpoints`` (there is no FK cascade
between them).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text

from vidyalaya_ai.db.engine import session_scope


logger = logging.getLogger("vidyalaya_ai.maintenance")

KEEP_LAST_N = 50
IDLE_EXPIRE_DAYS = 90


@dataclass(frozen=True)
class CleanupResult:
    """Counts of rows removed by a cleanup run."""

    checkpoints_deleted: int
    writes_deleted: int
    blobs_deleted: int


# Delete all but the newest N checkpoints per (thread_id, checkpoint_ns).
_PRUNE_KEEP_LAST = text(
    """
    DELETE FROM checkpoints c
    USING (
        SELECT thread_id, checkpoint_ns, checkpoint_id,
               ROW_NUMBER() OVER (
                   PARTITION BY thread_id, checkpoint_ns
                   ORDER BY checkpoint_id DESC
               ) AS rn
        FROM checkpoints
    ) ranked
    WHERE c.thread_id = ranked.thread_id
      AND c.checkpoint_ns = ranked.checkpoint_ns
      AND c.checkpoint_id = ranked.checkpoint_id
      AND ranked.rn > :keep_n
    """
)

# Delete every checkpoint of threads whose newest message is older than cutoff.
# Only threads that actually have messages are considered (no false expiry of a
# brand-new thread whose first message just landed).
_EXPIRE_IDLE = text(
    """
    DELETE FROM checkpoints c
    WHERE c.thread_id IN (
        SELECT thread_id
        FROM messages
        GROUP BY thread_id
        HAVING MAX(created_at) < now() - make_interval(days => :days)
    )
    """
)

# Sweep orphaned write/blob rows whose parent checkpoint is gone.
_SWEEP_WRITES = text(
    """
    DELETE FROM checkpoint_writes w
    WHERE NOT EXISTS (
        SELECT 1 FROM checkpoints c
        WHERE c.thread_id = w.thread_id
          AND c.checkpoint_ns = w.checkpoint_ns
          AND c.checkpoint_id = w.checkpoint_id
    )
    """
)

_SWEEP_BLOBS = text(
    """
    DELETE FROM checkpoint_blobs b
    WHERE NOT EXISTS (
        SELECT 1 FROM checkpoints c
        WHERE c.thread_id = b.thread_id
          AND c.checkpoint_ns = b.checkpoint_ns
    )
    """
)


async def run_checkpoint_cleanup(
    *,
    keep_last_n: int = KEEP_LAST_N,
    idle_expire_days: int = IDLE_EXPIRE_DAYS,
) -> CleanupResult:
    """Prune checkpoints, then sweep orphaned writes/blobs. Returns row counts.

    Idempotent and safe to run repeatedly (e.g. a daily cron). All passes run in
    a single transaction so the orphan sweep always sees the post-prune state.
    """
    async with session_scope() as session:
        pruned = await session.execute(
            _PRUNE_KEEP_LAST, {"keep_n": max(1, keep_last_n)}
        )
        expired = await session.execute(_EXPIRE_IDLE, {"days": max(1, idle_expire_days)})
        writes = await session.execute(_SWEEP_WRITES)
        blobs = await session.execute(_SWEEP_BLOBS)
        await session.commit()

        result = CleanupResult(
            checkpoints_deleted=(pruned.rowcount or 0) + (expired.rowcount or 0),
            writes_deleted=writes.rowcount or 0,
            blobs_deleted=blobs.rowcount or 0,
        )

    logger.info(
        "Checkpoint cleanup: checkpoints=%d writes=%d blobs=%d (keep_n=%d idle_days=%d)",
        result.checkpoints_deleted,
        result.writes_deleted,
        result.blobs_deleted,
        keep_last_n,
        idle_expire_days,
    )
    return result
