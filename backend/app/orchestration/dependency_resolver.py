"""Deterministic DAG dependency validation, cycle detection, and topological sorting."""

from typing import List, Dict, Set
from ..domain.models.workflow import TaskSpec, WorkflowSpec
from ..core.exceptions import WorkflowValidationError, CyclicDependencyError


class DependencyResolver:
    """Validates task dependencies and computes topological execution orders."""

    @staticmethod
    def validate_workflow_graph(workflow: WorkflowSpec) -> List[str]:
        """
        Statically validates task graph invariants:
        1. No duplicate task keys.
        2. No self-dependencies (task depending on itself).
        3. All dependencies reference valid task keys defined in the workflow.
        4. No circular dependencies (DAG invariant).

        Returns:
            List[str]: Topologically ordered list of task keys.
        """
        task_keys: Set[str] = set()
        for task in workflow.tasks:
            if task.task_key in task_keys:
                raise WorkflowValidationError(
                    f"Duplicate task_key '{task.task_key}' detected in workflow '{workflow.name}'."
                )
            task_keys.add(task.task_key)

        adjacency: Dict[str, List[str]] = {task.task_key: [] for task in workflow.tasks}
        in_degree: Dict[str, int] = {task.task_key: 0 for task in workflow.tasks}

        for task in workflow.tasks:
            for dep in task.depends_on:
                if dep == task.task_key:
                    raise WorkflowValidationError(
                        f"Task '{task.task_key}' has a self-dependency on itself."
                    )
                if dep not in task_keys:
                    raise WorkflowValidationError(
                        f"Task '{task.task_key}' depends on non-existent task '{dep}'."
                    )
                adjacency[dep].append(task.task_key)
                in_degree[task.task_key] += 1

        # Kahn's Algorithm for Topological Sort & Cycle Detection
        queue = [k for k, degree in in_degree.items() if degree == 0]
        topological_order: List[str] = []

        while queue:
            u = queue.pop(0)
            topological_order.append(u)
            for v in adjacency[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        if len(topological_order) != len(workflow.tasks):
            cyclic_keys = [k for k, degree in in_degree.items() if degree > 0]
            raise CyclicDependencyError(
                f"Circular dependency detected in workflow '{workflow.name}' involving tasks: {sorted(cyclic_keys)}."
            )

        return topological_order

    @staticmethod
    def get_ready_tasks(
        workflow: WorkflowSpec,
        completed_task_keys: Set[str],
        active_or_pending_task_keys: Set[str],
    ) -> List[TaskSpec]:
        """
        Identifies tasks whose dependencies are 100% completed and are ready to execute.
        """
        ready: List[TaskSpec] = []
        for task in workflow.tasks:
            if task.task_key in active_or_pending_task_keys:
                continue
            if all(dep in completed_task_keys for dep in task.depends_on):
                ready.append(task)
        return ready
