import { apiClient } from "./client";
import { EventListResponse } from "../types/api";

export async function getExecutionEvents(
  executionId: string
): Promise<EventListResponse> {
  return apiClient<EventListResponse>(`/executions/${executionId}/events`);
}
