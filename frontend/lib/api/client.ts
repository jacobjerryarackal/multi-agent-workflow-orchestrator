import { ApiErrorDetail, ErrorEnvelope } from "../types/api";

export class ApiClientError extends Error {
  public readonly code: string;
  public readonly status: number;
  public readonly details?: unknown;
  public readonly correlationId?: string;
  public readonly timestamp?: string;

  constructor(status: number, error: ApiErrorDetail) {
    super(error.message || `API request failed with status ${status}`);
    this.name = "ApiClientError";
    this.status = status;
    this.code = error.code || "UNKNOWN_ERROR";
    this.details = error.details;
    this.correlationId = error.correlation_id;
    this.timestamp = error.timestamp;
  }
}

// In Next.js client, relative path "/api/v1" is proxied by next.config.mjs rewrite to backend
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, headers, ...customConfig } = options;

  let url = `${BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val != null) {
        searchParams.append(key, String(val));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  const defaultHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  const config: RequestInit = {
    ...customConfig,
    headers: {
      ...defaultHeaders,
      ...headers,
    },
    cache: "no-store",
  };

  let response: Response;
  try {
    response = await fetch(url, config);
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Network error or backend unreachable.";
    throw new ApiClientError(0, {
      code: "NETWORK_ERROR",
      message: `Failed to connect to orchestrator backend: ${message}`,
    });
  }

  if (!response.ok) {
    let errorDetail: ApiErrorDetail;
    try {
      const data = await response.json();
      if (data && typeof data === "object" && "error" in data) {
        errorDetail = (data as ErrorEnvelope).error;
      } else if (data && typeof data === "object" && "detail" in data) {
        errorDetail = {
          code: `HTTP_${response.status}`,
          message: typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail),
        };
      } else {
        errorDetail = {
          code: `HTTP_${response.status}`,
          message: response.statusText || "Request failed",
        };
      }
    } catch {
      errorDetail = {
        code: `HTTP_${response.status}`,
        message: response.statusText || `Request failed with status ${response.status}`,
      };
    }

    throw new ApiClientError(response.status, errorDetail);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}
