# Recovery Strategies & Resilience Architecture

**Document:** Automated Recovery, Circuit Breaking & Human Escalation Mechanics  
**Status:** Approved Architecture (Day 0)  

---

## 1. Exponential Backoff with Decorrelated Jitter

To prevent the thundering herd problem during provider outages or rate limits, retries implement Full Jitter exponential backoff:

$$\text{Interval}_i = \min\left(\text{MaxInterval}, \text{Uniform}(0, \text{InitialInterval} \times \text{Multiplier}^i)\right)$$

```python
import random
import asyncio

async def retry_with_jitter(
    func, 
    max_attempts: int = 3, 
    initial_interval: float = 2.0, 
    multiplier: float = 2.0, 
    max_interval: float = 60.0
):
    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except Exception as exc:
            if attempt == max_attempts:
                raise exc
            backoff = min(max_interval, initial_interval * (multiplier ** (attempt - 1)))
            sleep_duration = random.uniform(0.5 * backoff, backoff)
            await asyncio.sleep(sleep_duration)
```

---

## 2. Rolling Circuit Breaker Pattern

When an external provider or agent exhibits sustained failure rates, the Circuit Breaker trips to protect backend resources and prevent quota waste:

```
          ┌────────────────────────────────────────────────────────┐
          │                                                        │
          │                   ┌──────────────┐                     │
          │     Success       │              │  Failures < Thresh  │
          └───────────────────│    CLOSED    │─────────────────────┘
                              │              │
                              └──────┬───────┘
                                     │
                                     │ Consecutive Failures >= 5
                                     ▼
                              ┌──────────────┐
                              │              │
                              │     OPEN     │◀────────────────────┐
                              │              │                     │
                              └──────┬───────┘                     │
                                     │                             │
                                     │ Cooldown Period Expired     │ Failure
                                     │ (e.g. 60s)                  │
                                     ▼                             │
                              ┌──────────────┐                     │
                              │              │                     │
                              │  HALF-OPEN   │─────────────────────┘
                              │              │
                              └──────┬───────┘
                                     │
                                     │ N Successful Probes
                                     ▼
                                  CLOSED
```

* **States**:
  - `CLOSED`: Normal operation. Failures are counted within a sliding 60-second window.
  - `OPEN`: Breaker tripped (e.g. >5 consecutive 5xx errors). Outbound calls immediately raise `CircuitBreakerOpenException` without calling the external API.
  - `HALF-OPEN`: Cooldown window (e.g. 60 seconds) elapsed. A single probe request is permitted. If successful, breaker resets to `CLOSED`; if it fails, breaker returns to `OPEN`.

---

## 3. Self-Correction & Reflection Prompt Loop

When an agent produces malformed JSON or fails Pydantic schema validation:
1. The error message and validation diff (e.g., `Missing required field 'sources_cited'`) are injected into a structured reflection prompt:
   ```
   Your previous response failed schema validation with error:
   {validation_error_message}
   
   Original input: {input_payload}
   Your invalid output: {invalid_output}
   
   Please correct the output to strictly conform to the required schema:
   {target_schema_json}
   ```
2. The agent is invoked with a single retry attempt.
3. If the second attempt fails schema validation, the task is routed to failure escalation.

---

## 4. Human-in-the-Loop Escalation Spectrum

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Tier 1: Full Automation         │ Routine tasks with verified deterministic I/O  │
│  Tier 2: Output Review Gate      │ High-stakes tasks awaiting human approval     │
│  Tier 3: Exception Escalation    │ Retry-exhausted or evaluator-rejected tasks   │
│  Tier 4: Emergency Abort         │ Manual operator cancellation of active DAG    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

When a task enters `WAITING_APPROVAL` or `ESCALATED`:
1. The workflow pauses execution on dependent downstream tasks.
2. Independent DAG branches continue executing concurrently.
3. An event `TASK_WAITING_APPROVAL` is broadcast to the Next.js control plane with complete task inputs, agent proposed output, and validation rationale.
4. An authorized operator can approve, reject, modify output, or re-route the task.
