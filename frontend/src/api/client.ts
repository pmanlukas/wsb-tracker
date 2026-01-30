import type {
  TickersResponse,
  TickerDetailResponse,
  SnapshotsResponse,
  ScanStartResponse,
  ScanStatus,
  AlertsResponse,
  StatsResponse,
} from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "";

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

// Ticker endpoints
export async function getTickers(
  hours: number = 24,
  limit: number = 25
): Promise<TickersResponse> {
  return fetchApi<TickersResponse>(
    `/api/tickers?hours=${hours}&limit=${limit}`
  );
}

export async function getTickerDetail(
  symbol: string,
  hours: number = 24
): Promise<TickerDetailResponse> {
  return fetchApi<TickerDetailResponse>(
    `/api/tickers/${symbol}?hours=${hours}`
  );
}

// Scan endpoints
export async function startScan(limit?: number): Promise<ScanStartResponse> {
  const params = limit ? `?limit=${limit}` : "";
  return fetchApi<ScanStartResponse>(`/api/scan${params}`, {
    method: "POST",
  });
}

export async function getScanStatus(scanId: string): Promise<ScanStatus> {
  return fetchApi<ScanStatus>(`/api/scan/${scanId}`);
}

export async function getSnapshots(limit: number = 10): Promise<SnapshotsResponse> {
  return fetchApi<SnapshotsResponse>(`/api/snapshots?limit=${limit}`);
}

// Alert endpoints
export async function getAlerts(
  unacknowledgedOnly: boolean = false,
  limit: number = 50
): Promise<AlertsResponse> {
  return fetchApi<AlertsResponse>(
    `/api/alerts?unacknowledged_only=${unacknowledgedOnly}&limit=${limit}`
  );
}

export async function acknowledgeAlert(alertId: number): Promise<void> {
  await fetchApi(`/api/alerts/${alertId}/ack`, {
    method: "POST",
  });
}

export async function acknowledgeAllAlerts(): Promise<void> {
  await fetchApi("/api/alerts/ack-all", {
    method: "POST",
  });
}

// Stats endpoints
export async function getStats(): Promise<StatsResponse> {
  return fetchApi<StatsResponse>("/api/stats");
}
