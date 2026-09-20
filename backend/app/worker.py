"""Autonomous reflection background worker."""

import asyncio
from typing import Optional
import structlog
from sqlmodel import Session as SQLModelSession, select

from app.config import settings
from app.db.session import engine, run_db
from app.models.memory import MemoryEpisodic
from app.services.reflection import ReflectionService

logger = structlog.get_logger(__name__)


def _check_pending_count(importance_threshold: float) -> int:
    """Return the number of unconsolidated episodic turns meeting the threshold.

    This is a plain synchronous function so it can be safely offloaded to a
    thread pool via ``run_db`` without holding the asyncio event loop.
    """
    with SQLModelSession(engine) as db:
        stmt = (
            select(MemoryEpisodic)
            .where(MemoryEpisodic.consolidated == False)  # noqa: E712
            .where(MemoryEpisodic.importance_score >= importance_threshold)
        )
        return len(list(db.exec(stmt).all()))


def _run_decay_pass(reflection_service: ReflectionService) -> dict:
    """Execute the confidence-decay pass in a dedicated session.

    Blocking DB writes are isolated here so the function can be offloaded to a
    thread pool via ``run_db`` without stalling the async event loop.
    """
    with SQLModelSession(engine) as decay_db:
        try:
            return reflection_service.decay_inactive_rules(db=decay_db)
        except Exception as d_exc:
            decay_db.rollback()
            raise d_exc


class AutonomousReflectionWorker:
    """Periodically scans for unconsolidated episodic interactions and executes reflection."""

    def __init__(
        self,
        interval_seconds: int = 60,
        importance_threshold: float = 0.50,
    ) -> None:
        self.interval_seconds = interval_seconds
        self.importance_threshold = importance_threshold
        self.reflection_service = ReflectionService()
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Run the worker loop until cancelled."""
        self.is_running = True
        logger.info(
            "Starting AutonomousReflectionWorker",
            interval_seconds=self.interval_seconds,
            threshold=self.importance_threshold,
        )

        while self.is_running:
            try:
                # 1. Check for unconsolidated candidate turns — offloaded to a
                #    thread pool so the blocking SQLModel query does not stall
                #    the asyncio event loop.
                pending_count = 0
                try:
                    pending_count = await run_db(_check_pending_count, self.importance_threshold)
                except Exception as check_exc:
                    logger.error("Failed to check unconsolidated turns in worker", error=str(check_exc))

                # 2. Reflection consolidation pass.
                #    NOT thread-offloaded: consolidate() interleaves multiple
                #    awaited LLM API calls (embeddings + generation) and holds
                #    the asyncio _consolidation_lock across those awaits.  Pushing
                #    it to a thread would require re-entrant locking and defeat
                #    the cross-coroutine concurrency guard.
                if pending_count > 0:
                    logger.info(
                        "Autonomous worker detected unconsolidated turns; triggering consolidation",
                        pending_count=pending_count,
                    )
                    try:
                        with SQLModelSession(engine) as cons_db:
                            try:
                                result = await self.reflection_service.consolidate(
                                    db=cons_db,
                                    importance_threshold=self.importance_threshold,
                                )
                                logger.info(
                                    "Autonomous reflection cycle completed",
                                    processed=result.get("processed_episodic_count"),
                                    procedural=result.get("procedural_created_count"),
                                    semantic=result.get("semantic_created_count"),
                                )
                            except Exception as c_exc:
                                cons_db.rollback()
                                logger.error("Error during autonomous consolidation; session rolled back", error=str(c_exc))
                    except Exception as sess_exc:
                        logger.error("Session checkout error during consolidation", error=str(sess_exc))

                # 3. Confidence-decay pass — offloaded to a thread pool so the
                #    blocking SQLModel writes + Qdrant payload syncs do not stall
                #    the asyncio event loop.
                try:
                    decay_res = await run_db(_run_decay_pass, self.reflection_service)
                    if decay_res.get("decayed_count", 0) > 0 or decay_res.get("archived_count", 0) > 0:
                        logger.info(
                            "Autonomous decay pass completed",
                            decayed=decay_res.get("decayed_count"),
                            archived=decay_res.get("archived_count"),
                        )
                except Exception as d_exc:
                    logger.error("Error during autonomous decay pass", error=str(d_exc))

                # 4. Periodic Postgres → Qdrant reconciliation pass.
                #    NOT thread-offloaded: sync_all_rules_to_qdrant() is async
                #    and may itself await embed_text() for any rules missing from
                #    Qdrant.  Mixing asyncio awaits inside asyncio.to_thread is
                #    unsupported; the function must run on the main event loop.
                try:
                    with SQLModelSession(engine) as sync_db:
                        try:
                            await self.reflection_service.sync_all_rules_to_qdrant(db=sync_db)
                        except Exception as s_exc:
                            sync_db.rollback()
                            logger.warning("Periodic Qdrant reconciliation failed; session rolled back", error=str(s_exc))
                except Exception as sess_exc:
                    logger.warning("Session checkout error during reconciliation", error=str(sess_exc))

            except asyncio.CancelledError:
                logger.info("AutonomousReflectionWorker cancelled")
                break
            except Exception as exc:
                logger.error("Error in autonomous reflection loop", error=str(exc))

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

        self.is_running = False
        logger.info("AutonomousReflectionWorker stopped")

    def stop(self) -> None:
        """Signal the worker to stop."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()


reflection_worker = AutonomousReflectionWorker(
    interval_seconds=int(getattr(settings, "REFLECTION_INTERVAL_SECONDS", 60)),
    importance_threshold=0.50,
)
