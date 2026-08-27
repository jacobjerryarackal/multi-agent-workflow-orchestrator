import { apiClient } from "./client";
import {
  WorkflowCreateRequest,
  WorkflowListResponse,
  WorkflowResponse,
} from "../types/api";

export async function getWorkflows(params?: {
  limit?: number;
  offset?: number;
}): Promise<WorkflowListResponse> {
  return apiClient<WorkflowListResponse>("/workflows", { params });
}

export async function getWorkflow(id: string): Promise<WorkflowResponse> {
  return apiClient<WorkflowResponse>(`/workflows/${id}`);
}

export async function createWorkflow(
  payload: WorkflowCreateRequest
): Promise<WorkflowResponse> {
  return apiClient<WorkflowResponse>("/workflows", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
