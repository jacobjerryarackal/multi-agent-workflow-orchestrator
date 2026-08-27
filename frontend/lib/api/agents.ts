import { apiClient } from "./client";
import { AgentListResponse, AgentSummaryResponse } from "../types/api";

export async function getAgents(): Promise<AgentListResponse> {
  return apiClient<AgentListResponse>("/agents");
}

export async function getAgent(agentId: string): Promise<AgentSummaryResponse> {
  return apiClient<AgentSummaryResponse>(`/agents/${agentId}`);
}
