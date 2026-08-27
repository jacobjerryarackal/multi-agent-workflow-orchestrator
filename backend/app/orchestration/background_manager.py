"""Background execution supervisor, async worker pool, and watchdog for stale task recovery."""

import asyncio
from datetime import datetime
from typing import Any, Callable, Optional, Set
import structlog

from ..core.config import settings
from ..core.telemetry import telemetry
from ..domain.interfaces.model_provider import ModelProvider
from ..domain.interfaces.evaluation_provider import EvaluationProvider
from ..persistence.database import async_session_factory
from ..persistence.repositories import (
    SqlWorkflowRepository,
    SqlExecutionRepository,
    SqlEventRepository,
    SqlArtifactRepository,
)
from ..agents.registry import AgentRegistry
from ..agents.builtins import (
    PlannerAgent,
    ResearcherAgent,
    AnalystAgent,
    ReviewerAgent,
    SynthesizerAgent,
)
from ..providers.gemini import GeminiModelProvider
from ..evaluators.composite import CompositeQualityEvaluator
from .execution_engine import WorkflowExecutionEngine
from ..api.middleware.correlation import get_correlation_id, set_correlation_id

logger = structlog.get_logger(__name__)

# Global singleton background execution manager
_global_background_manager: Optional["BackgroundExecutionManager"] = None


def get_background_manager() -> "BackgroundExecutionManager":
    """Retrieves or initializes the global singleton BackgroundExecutionManager."""
    global _global_background_manager
    if _global_background_manager is None:
        _global_background_manager = BackgroundExecutionManager()
    return _global_background_manager


def set_background_manager(manager: Optional["BackgroundExecutionManager"]) -> None:
    """Explicitly sets or resets the global BackgroundExecutionManager instance (used in tests)."""
    global _global_background_manager
    _global_background_manager = manager


class BackgroundExecutionManager:
    """
    Manages in-process asynchronous workflow execution tasks, background scheduling,
    periodic watchdog inspection for expired task leases, and graceful shutdown.
    """

    def __init__(
        self,
        session_factory: Optional[Callable[[], Any]] = None,
        model_provider: Optional[ModelProvider] = None,
        evaluator: Optional[EvaluationProvider] = None,
    ):
        self._session_factory = session_factory
        self.model_provider = model_provider
        self.evaluator = evaluator
        self._active_tasks: Set[asyncio.Task] = set()
        self._running_execution_ids: Set[str] = set()
        self._watchdog_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

    def _get_provider(self) -> ModelProvider:
        if self.model_provider is None:
            self.model_provider = GeminiModelProvider(api_key=settings.GEMINI_API_KEY)
        return self.model_provider

    def _get_registry(self) -> AgentRegistry:
        provider = self._get_provider()
        registry = AgentRegistry()
        registry.register(PlannerAgent(model_provider=provider))
        registry.register(ResearcherAgent(model_provider=provider))
        registry.register(AnalystAgent(model_provider=provider))
        registry.register(ReviewerAgent(model_provider=provider))
        registry.register(SynthesizerAgent(model_provider=provider))
        return registry

    def _get_evaluator(self) -> EvaluationProvider:
        if self.evaluator is None:
            provider = self._get_provider()
            self.evaluator = CompositeQualityEvaluator(model_provider=provider)
        return self.evaluator

    def schedule_execution(
        self,
        execution_id: str,
        correlation_id: Optional[str] = None,
        registry: Optional[AgentRegistry] = None,
        evaluator: Optional[EvaluationProvider] = None,
        session_factory: Optional[Callable[[], Any]] = None,
    ) -> Optional[asyncio.Task]:
        """
        Schedules an asynchronous background execution task using an isolated session.
        Preserves correlation ID, agent registry overrides, and evaluation providers.
        """
        if self._shutdown_event.is_set():
            telemetry.increment_counter("background_dispatch_failures_total")
            logger.warning("Rejecting execution schedule during shutdown", execution_id=execution_id)
            return None

        if execution_id in self._running_execution_ids:
            logger.info("Execution is already running in background", execution_id=execution_id)
            return None

        cid = correlation_id or get_correlation_id()
        task = asyncio.create_task(
            self._execute_workflow_coroutine(
                execution_id=execution_id,
                correlation_id=cid,
                registry=registry,
                evaluator=evaluator,
                session_factory=session_factory,
            ),
            name=f"wf-exec-{execution_id}",
        )
        self._active_tasks.add(task)
        self._running_execution_ids.add(execution_id)
        telemetry.increment_counter("background_dispatch_total")
        telemetry.set_gauge("background_active_executions", float(len(self._active_tasks)))

        task.add_done_callback(lambda t: self._cleanup_task(t, execution_id))
        return task

    def _cleanup_task(self, task: asyncio.Task, execution_id: str) -> None:
        self._active_tasks.discard(task)
        self._running_execution_ids.discard(execution_id)
        telemetry.set_gauge("background_active_executions", float(len(self._active_tasks)))
        if not task.cancelled() and task.exception():
            logger.error(
                "Background workflow execution task failed with unhandled exception",
                execution_id=execution_id,
                error=str(task.exception()),
            )

    async def _execute_workflow_coroutine(
        self,
        execution_id: str,
        correlation_id: str,
        registry: Optional[AgentRegistry] = None,
        evaluator: Optional[EvaluationProvider] = None,
        session_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        """Coroutine driving WorkflowExecutionEngine in an isolated session."""
        set_correlation_id(correlation_id)
        logger.info("Starting background workflow execution", execution_id=execution_id, correlation_id=correlation_id)

        factory = session_factory or self._session_factory or async_session_factory
        async with factory() as session:
            try:
                workflow_repo = SqlWorkflowRepository(session)
                execution_repo = SqlExecutionRepository(session)
                event_repo = SqlEventRepository(session)
                artifact_repo = SqlArtifactRepository(session)
                reg = registry or self._get_registry()
                eval_prov = evaluator or self._get_evaluator()

                engine = WorkflowExecutionEngine(
                    workflow_repo=workflow_repo,
                    execution_repo=execution_repo,
                    event_repo=event_repo,
                    artifact_repo=artifact_repo,
                    agent_registry=reg,
                    evaluator=eval_prov,
                )

                await engine.run_to_completion(execution_id)
                await session.commit()
                logger.info("Background workflow execution completed", execution_id=execution_id)
            except Exception as exc:
                await session.rollback()
                logger.error(
                    "Background workflow execution encountered error",
                    execution_id=execution_id,
                    error=str(exc),
                )

    async def recover_stranded_executions(
        self,
        session_factory: Optional[Callable[[], Any]] = None,
    ) -> int:
        """
        Scans for expired task leases and stranded QUEUED/RUNNING workflows.
        Reclaims stale tasks and resumes eligible workflow executions.
        """
        factory = session_factory or self._session_factory or async_session_factory
        async with factory() as session:
            try:
                workflow_repo = SqlWorkflowRepository(session)
                execution_repo = SqlExecutionRepository(session)
                event_repo = SqlEventRepository(session)
                artifact_repo = SqlArtifactRepository(session)
                registry = self._get_registry()
                evaluator = self._get_evaluator()

                engine = WorkflowExecutionEngine(
                    workflow_repo=workflow_repo,
                    execution_repo=execution_repo,
                    event_repo=event_repo,
                    artifact_repo=artifact_repo,
                    agent_registry=registry,
                    evaluator=evaluator,
                )

                telemetry.increment_counter("background_watchdog_sweeps_total")

                # 1. Recover stale tasks with expired leases
                stale_reclaimed = await engine.recover_stale_tasks()
                if stale_reclaimed > 0:
                    telemetry.increment_counter("background_tasks_recovered_total", value=float(stale_reclaimed))

                # 2. Check for active/stranded workflows that need execution driving
                active_execution_ids = await execution_repo.get_active_workflow_execution_ids()
                await session.commit()

                resumed_count = 0
                for exec_id in active_execution_ids:
                    if exec_id not in self._running_execution_ids and not self._shutdown_event.is_set():
                        self.schedule_execution(exec_id, session_factory=factory)
                        resumed_count += 1

                if stale_reclaimed > 0 or resumed_count > 0:
                    logger.info(
                        "Recovery sweep completed",
                        stale_reclaimed=stale_reclaimed,
                        resumed_workflows=resumed_count,
                    )
                return stale_reclaimed + resumed_count
            except Exception as exc:
                await session.rollback()
                logger.error("Error during recovery sweep", error=str(exc))
                return 0

    def start_watchdog(self, interval_seconds: float = 10.0) -> None:
        """Starts periodic background watchdog loop."""
        if self._watchdog_task is None or self._watchdog_task.done():
            self._shutdown_event.clear()
            self._watchdog_task = asyncio.create_task(
                self._watchdog_loop(interval_seconds),
                name="stale-task-watchdog",
            )
            logger.info("Stale task watchdog supervisor started", interval_seconds=interval_seconds)

    async def _watchdog_loop(self, interval_seconds: float) -> None:
        """Periodic loop scanning for expired leases."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(interval_seconds)
                if not self._shutdown_event.is_set():
                    await self.recover_stranded_executions()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Watchdog loop cycle error", error=str(exc))

    async def stop_watchdog(self) -> None:
        """Stops the periodic watchdog task."""
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None
            logger.info("Stale task watchdog supervisor stopped")

    async def graceful_shutdown(self, timeout_seconds: float = 5.0) -> None:
        """Initiates graceful shutdown: stops watchdog, awaits in-flight executions up to timeout."""
        logger.info("Initiating background execution manager graceful shutdown", active_tasks=len(self._active_tasks))
        telemetry.increment_counter("background_shutdowns_total")
        self._shutdown_event.set()
        await self.stop_watchdog()

        try:
            current_loop = asyncio.get_running_loop()
            active_in_loop = {
                t for t in self._active_tasks
                if not t.done() and getattr(t, "get_loop", lambda: current_loop)() == current_loop
            }
        except RuntimeError:
            active_in_loop = set()

        if active_in_loop:
            # Wait for active tasks to conclude within timeout
            done, pending = await asyncio.wait(
                active_in_loop,
                timeout=timeout_seconds,
                return_when=asyncio.ALL_COMPLETED,
            )
            if pending:
                logger.warning(
                    "Canceling remaining in-flight background execution tasks after shutdown timeout",
                    count=len(pending),
                )
                for task in pending:
                    task.cancel()
        self._active_tasks.clear()
        self._running_execution_ids.clear()
        telemetry.set_gauge("background_active_executions", 0.0)
