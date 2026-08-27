import { apiClient } from "./client";
import { ArtifactContentResponse, ArtifactListResponse } from "../types/api";

export async function getExecutionArtifacts(
  executionId: string
): Promise<ArtifactListResponse> {
  return apiClient<ArtifactListResponse>(
    `/executions/${executionId}/artifacts`
  );
}

export async function getArtifactContent(
  executionId: string,
  artifactId: string
): Promise<ArtifactContentResponse> {
  return apiClient<ArtifactContentResponse>(
    `/executions/${executionId}/artifacts/${artifactId}`
  );
}
