import { apiClient } from "./client";
import { HealthResponse, TelemetrySnapshotResponse } from "../types/api";

export async function getSystemHealth(): Promise<HealthResponse> {
  return apiClient<HealthResponse>("/health");
}

export async function getSystemTelemetry(): Promise<TelemetrySnapshotResponse> {
  return apiClient<TelemetrySnapshotResponse>("/telemetry");
}
