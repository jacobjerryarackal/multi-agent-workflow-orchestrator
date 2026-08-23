# Execution Model: Multi-Agent Workflow Orchestrator

**Document:** DAG Dependency Resolution, Dispatching & Bound Constraints  
**Status:** Approved Architecture (Day 0)  

---

## 1. DAG Dependency Resolution Algorithm

The workflow engine models task execution as a Directed Acyclic Graph $G = (V, E)$, where vertices $V$ are task specifications and directed edges $E = (u, v)$ represent dependencies (task $v$ depends on task $u$).

### 1.1 Cycle Detection & Validation (Registration Phase)
Before persisting or executing any workflow, the engine performs Kahn's Algorithm for topological sorting and cycle detection:

```python
def validate_and_toposort(tasks: list[TaskSpec]) -> list[str]:
    in_degree = {task.key: 0 for task in tasks}
    adjacency = {task.key: [] for task in tasks}
    
    for task in tasks:
        for dep in task.depends_on:
            if dep not in in_degree:
                raise ValueError(f"Task '{task.key}' depends on non-existent task '{dep}'")
            adjacency[dep].append(task.key)
            in_degree[task.key] += 1
            
    queue = [task_key for task_key, degree in in_degree.items() if degree == 0]
    ordered = []
    
    while queue:
        u = queue.pop(0)
        ordered.append(u)
        for v in adjacency[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
                
    if len(ordered) != len(tasks):
        cyclic_tasks = [k for k, d in in_degree.items() if d > 0]
        raise CyclicDependencyError(f"Circular dependency detected involving: {cyclic_tasks}")
        
    return ordered
```

---

## 2. Dynamic Execution Loop & Async Dispatching

The Orchestration Engine runs an asynchronous event-driven scheduling loop:

```
                  ┌─────────────────────────────────────┐
                  │        Orchestrator Tick Loop       │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │ 1. Fetch In-Flight Workflow State   │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │ 2. Find All Tasks with In-Degree 0  │
                  │    (All Upstream Dependencies Done) │
                  └──────────────────┬──────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │ Ready Tasks Found               │ No Tasks Ready
                    ▼                                 ▼
┌───────────────────────────────────────┐   ┌─────────────────────────────────────┐
│ 3. Check Parallel Limit (Semaphore)   │   │ Check for Terminal Condition:       │
│    Dispatch Tasks in Asyncio Tasks    │   │ • All tasks COMPLETED -> Finish     │
└──────────────────┬────────────────────┘   │ • Any fatal FAILED -> Fail Workflow │
                   │                        │ • Any WAITING_APPROVAL -> Pause     │
                   ▼                        └─────────────────────────────────────┘
┌───────────────────────────────────────┐
│ 4. Task Worker Execution:             │
│    • Resolve upstream artifacts       │
│    • Validate input schema            │
│    • Call Agent via ModelProvider     │
│    • Validate output schema           │
│    • Run Quality Evaluator Gate       │
│    • Persist artifacts & output       │
│    • Update Task State (COMPLETED)    │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│ 5. Emit WorkflowEvent & Trigger Next  │
│    Scheduler Tick                     │
└───────────────────────────────────────┘
```

---

## 3. Artifact & Context Data Flow

Tasks communicate without shared global mutation through explicit artifact and data references:

1. **Explicit Data Mapping**: A task specification can bind its inputs to upstream task outputs using JSONPath syntax:
   ```json
   {
     "task_key": "synthesizer_task",
     "agent_id": "synthesizer_agent",
     "depends_on": ["research_a", "research_b"],
     "input_mappings": {
       "primary_findings": "$.tasks.research_a.outputs.findings",
       "secondary_findings": "$.tasks.research_b.outputs.findings",
       "attached_documents": "$.artifacts.by_task['research_a']"
     }
   }
   ```
2. **Artifact Immutability**: Artifacts generated during task execution are assigned unique UUIDs and SHA-256 content hashes, stored in PostgreSQL/object storage, and passed immutably to downstream tasks.

---

## 4. Controlled Loop Boundaries (Genesis-Style Constraints)

To prevent runaway agent recursion, resource exhaustion, or infinite loops, the engine enforces 7 strict runtime boundaries:

| Boundary Parameter | Default Value | Hard Maximum | Action on Breach |
| :--- | :--- | :--- | :--- |
| `max_workflow_duration` | 600s (10 min) | 3600s (1 hour) | Workflow terminates with `TIMED_OUT` event. |
| `max_task_duration` | 60s (1 min) | 300s (5 min) | Task cancelled, marked `TIMED_OUT`, triggers retry/failure. |
| `max_parallel_tasks` | 5 concurrent | 20 concurrent | Backpressure applied; tasks queued until worker capacity frees. |
| `max_task_retries` | 3 attempts | 5 attempts | Exhaustion marks task as `FAILED` and escalates. |
| `max_total_workflow_steps`| 50 steps | 200 steps | Prevents dynamic sub-task explosion. |
| `max_output_size_bytes` | 1 MB | 10 MB | Rejects malformed or context-overflow outputs. |
| `max_agent_loop_iterations`| 5 iterations | 10 iterations | Single-agent internal reflection bounded. |
