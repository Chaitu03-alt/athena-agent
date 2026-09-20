"""Autonomous reflection background worker."""

import asyncio
from typing import Optional
import structlog
from sqlmodel import Session as SQLModelSession, select

from app.config import settings
from app.db.session import engine
from app.models.memory import MemoryEpisodic
from app.services.reflection import ReflectionService

logger = structlog.get_logger(__name__)


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
                # 1. Isolated session for checking unconsolidated candidate turns
                pending_count = 0
                try:
                    with SQLModelSession(engine) as check_db:
                        stmt = (
                            select(MemoryEpisodic)
                            .where(MemoryEpisodic.consolidated == False)  # noqa: E712
                            .where(MemoryEpisodic.importance_score >= self.importance_threshold)
                        )
                        pending_count = len(list(check_db.exec(stmt).all()))
                except Exception as check_exc:
                    logger.error("Failed to check unconsolidated turns in worker", error=str(check_exc))

                # 2. Isolated session for reflection consolidation pass
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

                # 3. Isolated session for procedural memory confidence decay pass
                try:
                    with SQLModelSession(engine) as decay_db:
                        try:
                            decay_res = self.reflection_service.decay_inactive_rules(db=decay_db)
                            if decay_res.get("decayed_count", 0) > 0 or decay_res.get("archived_count", 0) > 0:
                                logger.info(
                                    "Autonomous decay pass completed",
                                    decayed=decay_res.get("decayed_count"),
                                    archived=decay_res.get("archived_count"),
                                )
                        except Exception as d_exc:
                            decay_db.rollback()
                            logger.error("Error during autonomous decay pass; session rolled back", error=str(d_exc))
                except Exception as sess_exc:
                    logger.error("Session checkout error during decay pass", error=str(sess_exc))

                # 4. Periodic auto-reconciliation pass between Postgres and Qdrant
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
