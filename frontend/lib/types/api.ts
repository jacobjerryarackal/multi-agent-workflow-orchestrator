/**
 * Strongly-typed API DTOs exactly mirroring Phase 6.2 backend Pydantic schemas.
 */

export type WorkflowExecutionStatusType =
  | "QUEUED"
  | "RUNNING"
  | "PAUSED"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "TIMED_OUT";

export type TaskExecutionStatusType =
  | "PENDING"
  | "BLOCKED"
  | "READY"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "WAITING_APPROVAL"
  | "ESCALATED"
  | "TIMED_OUT"
  | "CANCELLED";

export type EventTypeEnum =
  | "WORKFLOW_SUBMITTED"
  | "WORKFLOW_STARTED"
  | "WORKFLOW_PAUSED"
  | "WORKFLOW_RESUMED"
  | "WORKFLOW_COMPLETED"
  | "WORKFLOW_FAILED"
  | "WORKFLOW_CANCELLED"
  | "WORKFLOW_TIMED_OUT"
  | "TASK_SCHEDULED"
  | "TASK_READY"
  | "TASK_STARTED"
  | "TASK_COMPLETED"
  | "TASK_FAILED"
  | "TASK_RETRIED"
  | "TASK_CANCELLED"
  | "TASK_TIMED_OUT"
  | "TASK_WAITING_APPROVAL"
  | "APPROVAL_DECISION_RECORDED"
  | "EVALUATION_GATE_SCORED"
  | "EVALUATION_STARTED"
  | "EVALUATION_COMPLETED"
  | "EVALUATION_PASSED"
  | "REVISION_REQUESTED"
  | "EVALUATION_FAILED"
  | "EVALUATION_ESCALATED"
  | "ARTIFACT_PRODUCED"
  | "CIRCUIT_BREAKER_TRIGGERED"
  | "STATE_CHECKPOINT_SAVED";

export interface RetryPolicySchema {
  max_attempts: number;
  initial_interval_seconds: number;
  backoff_multiplier: number;
  jitter: boolean;
  retryable_categories: string[];
}

export interface ApprovalGateSchema {
  required: boolean;
  approver_roles: string[];
  timeout_seconds: number;
  auto_action_on_timeout: string;
}

export interface EvaluationGateSchema {
  enabled: boolean;
  evaluator_name: string;
  min_pass_score: number;
  max_revisions: number;
  deterministic_rules: string[];
  criteria: Record<string, unknown>;
  rejection_policy: string;
}

export interface TaskSpecSchema {
  task_key: string;
  name: string;
  agent_id: string;
  depends_on: string[];
  input_mappings: Record<string, string>;
  static_inputs: Record<string, unknown>;
  timeout_seconds: number;
  retry_policy?: RetryPolicySchema;
  approval_gate?: ApprovalGateSchema;
  evaluation_gate?: EvaluationGateSchema;
}

export interface WorkflowCreateRequest {
  name: string;
  version?: number;
  description: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  tasks: TaskSpecSchema[];
  max_workflow_duration_seconds?: number;
  max_parallel_tasks?: number;
}

export interface WorkflowResponse {
  id: string;
  name: string;
  version: number;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  tasks: TaskSpecSchema[];
  max_workflow_duration_seconds: number;
  max_parallel_tasks: number;
  created_at: string;
}

export interface WorkflowListResponse {
  items: WorkflowResponse[];
  total_count: number;
}

export interface SubmitExecutionRequest {
  input_data?: Record<string, unknown>;
  idempotency_key?: string | null;
  trigger_type?: string;
}

export interface TaskExecutionSummaryResponse {
  id: string;
  workflow_execution_id: string;
  task_key: string;
  agent_id: string;
  status: TaskExecutionStatusType;
  attempt_count: number;
  revision_count: number;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  evaluation_history: Array<Record<string, unknown>>;
  error_details: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  execution_duration_ms: number | null;
  token_usage: Record<string, number>;
}

export interface WorkflowExecutionSummaryResponse {
  id: string;
  workflow_id: string;
  status: WorkflowExecutionStatusType;
  trigger_type: string;
  idempotency_key: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  execution_duration_ms: number | null;
  error_summary: string | null;
}

export interface WorkflowExecutionDetailResponse {
  id: string;
  workflow_id: string;
  status: WorkflowExecutionStatusType;
  trigger_type: string;
  idempotency_key: string | null;
  initial_inputs: Record<string, unknown>;
  final_outputs: Record<string, unknown>;
  error_summary: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  execution_duration_ms: number | null;
  tasks: TaskExecutionSummaryResponse[];
}

export interface ExecutionListResponse {
  items: WorkflowExecutionSummaryResponse[];
  total_count: number;
}

export interface TaskApproveRequest {
  approver?: string;
  comment?: string | null;
}

export interface TaskRejectRequest {
  rejector?: string;
  reason: string;
}

export interface EventResponse {
  id: string;
  workflow_execution_id: string;
  task_execution_id: string | null;
  task_key: string | null;
  event_type: EventTypeEnum;
  actor: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface EventListResponse {
  items: EventResponse[];
  total_count: number;
}

export interface ArtifactResponse {
  id: string;
  workflow_execution_id: string;
  task_key: string | null;
  task_execution_id: string | null;
  artifact_name: string;
  artifact_type: string;
  content_hash: string;
  size_bytes: number;
  storage_uri: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ArtifactListResponse {
  items: ArtifactResponse[];
  total_count: number;
}

export interface ArtifactContentResponse {
  artifact_id: string;
  artifact_name: string;
  artifact_type: string;
  content_hash: string;
  verified: boolean;
  data: unknown;
}

export interface AgentSummaryResponse {
  agent_id: string;
  name: string;
  description: string;
  version: string;
  capabilities: string[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
}

export interface AgentListResponse {
  items: AgentSummaryResponse[];
  total_count: number;
}

export interface HealthComponentStatus {
  status: "healthy" | "degraded" | "unavailable";
  details?: Record<string, unknown>;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unavailable";
  version: string;
  timestamp: string;
  correlation_id: string;
  components: Record<string, HealthComponentStatus>;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: unknown;
  correlation_id?: string;
  timestamp?: string;
}

export interface ErrorEnvelope {
  error: ApiErrorDetail;
}

export interface MetricItem {
  metric_name: string;
  labels: Record<string, string>;
  value?: number;
  count?: number;
  sum?: number;
}

export interface TelemetrySnapshotResponse {
  app_name: string;
  timestamp: string;
  counters: Record<string, MetricItem[]>;
  gauges: Record<string, MetricItem[]>;
  histograms: Record<string, MetricItem[]>;
}
