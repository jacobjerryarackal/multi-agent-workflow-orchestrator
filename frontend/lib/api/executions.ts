import { apiClient } from "./client";
import {
  ExecutionListResponse,
  SubmitExecutionRequest,
  TaskApproveRequest,
  TaskExecutionSummaryResponse,
  TaskRejectRequest,
  WorkflowExecutionDetailResponse,
  WorkflowExecutionSummaryResponse,
} from "../types/api";

export async function getExecutions(params?: {
  workflow_id?: string;
  limit?: number;
  offset?: number;
}): Promise<ExecutionListResponse> {
  return apiClient<ExecutionListResponse>("/executions", { params });
}

export async function getExecution(
  id: string
): Promise<WorkflowExecutionDetailResponse> {
  return apiClient<WorkflowExecutionDetailResponse>(`/executions/${id}`);
}

export async function submitWorkflowExecution(
  workflowId: string,
  payload: SubmitExecutionRequest
): Promise<WorkflowExecutionDetailResponse> {
  return apiClient<WorkflowExecutionDetailResponse>(
    `/workflows/${workflowId}/executions`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function cancelExecution(
  id: string
): Promise<WorkflowExecutionSummaryResponse> {
  return apiClient<WorkflowExecutionSummaryResponse>(
    `/executions/${id}/cancel`,
    {
      method: "POST",
    }
  );
}

export async function approveTask(
  executionId: string,
  taskKey: string,
  payload: TaskApproveRequest = {}
): Promise<TaskExecutionSummaryResponse> {
  return apiClient<TaskExecutionSummaryResponse>(
    `/executions/${executionId}/tasks/${taskKey}/approve`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function rejectTask(
  executionId: string,
  taskKey: string,
  payload: TaskRejectRequest
): Promise<TaskExecutionSummaryResponse> {
  return apiClient<TaskExecutionSummaryResponse>(
    `/executions/${executionId}/tasks/${taskKey}/reject`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}
