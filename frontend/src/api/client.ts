import type {
  TickersResponse,
  TickerDetailResponse,
  SnapshotsResponse,
  ScanStartResponse,
  ScanStatus,
  AlertsResponse,
  StatsResponse,
  MentionsListResponse,
  MentionFilters,
  FilterOptions,
  ScanSettings,
  ScanSettingsUpdate,
  TradingIdea,
  TradingIdeasListResponse,
  TradingIdeasSummary,
  TradingIdeasFilters,
  TradingIdeasFilterOptions,
  LLMStatus,
  LLMUsageResponse,
  PriceData,
  PricesBatchResponse,
  SparklineData,
  CorrelationResponse,
  CooccurrenceResponse,
  CorrelationMatrixResponse,
  CorrelationFilters,
  OutcomeRequest,
  PerformanceStats,
  TradingIdeaWithOutcome,
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

// ==================== MENTIONS ENDPOINTS ====================

export async function getMentions(
  page: number = 1,
  pageSize: number = 50,
  filters: MentionFilters
): Promise<MentionsListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort_by: filters.sortBy,
    sort_order: filters.sortOrder,
  });

  if (filters.ticker) params.append("ticker", filters.ticker);
  if (filters.subreddit) params.append("subreddit", filters.subreddit);
  if (filters.dateFrom) params.append("date_from", filters.dateFrom);
  if (filters.dateTo) params.append("date_to", filters.dateTo);
  if (filters.sentimentMin !== undefined)
    params.append("sentiment_min", String(filters.sentimentMin));
  if (filters.sentimentMax !== undefined)
    params.append("sentiment_max", String(filters.sentimentMax));

  return fetchApi<MentionsListResponse>(`/api/mentions?${params}`);
}

export async function deleteMention(mentionId: number): Promise<void> {
  await fetchApi(`/api/mentions/${mentionId}`, { method: "DELETE" });
}

export async function deleteMentionsBulk(
  mentionIds: number[]
): Promise<{ deleted_count: number }> {
  return fetchApi("/api/mentions/delete-bulk", {
    method: "POST",
    body: JSON.stringify({ mention_ids: mentionIds }),
  });
}

export async function getFilterOptions(): Promise<FilterOptions> {
  return fetchApi<FilterOptions>("/api/mentions/filter-options");
}

// ==================== SETTINGS ENDPOINTS ====================

export async function getScanSettings(): Promise<ScanSettings> {
  return fetchApi<ScanSettings>("/api/settings/scan");
}

export async function updateScanSettings(
  settings: ScanSettingsUpdate
): Promise<ScanSettings> {
  return fetchApi<ScanSettings>("/api/settings/scan", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

export async function resetScanSettings(): Promise<ScanSettings> {
  return fetchApi<ScanSettings>("/api/settings/scan/reset", {
    method: "POST",
  });
}

// ==================== TRADING IDEAS ENDPOINTS ====================

export async function getTradingIdeas(
  page: number = 1,
  pageSize: number = 25,
  filters: TradingIdeasFilters = {}
): Promise<TradingIdeasListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  if (filters.ticker) params.append("ticker", filters.ticker);
  if (filters.direction) params.append("direction", filters.direction);
  if (filters.conviction) params.append("conviction", filters.conviction);
  if (filters.postType) params.append("post_type", filters.postType);
  if (filters.minQuality !== undefined)
    params.append("min_quality", String(filters.minQuality));
  if (filters.actionableOnly) params.append("actionable_only", "true");
  if (filters.hours) params.append("hours", String(filters.hours));

  return fetchApi<TradingIdeasListResponse>(`/api/trading-ideas?${params}`);
}

export async function getTradingIdeasSummary(
  hours: number = 24
): Promise<TradingIdeasSummary> {
  return fetchApi<TradingIdeasSummary>(
    `/api/trading-ideas/summary?hours=${hours}`
  );
}

export async function getTradingIdeasFilterOptions(): Promise<TradingIdeasFilterOptions> {
  return fetchApi<TradingIdeasFilterOptions>("/api/trading-ideas/filters");
}

export async function getTradingIdeasByTicker(
  ticker: string,
  hours: number = 24,
  limit: number = 20
): Promise<TradingIdea[]> {
  return fetchApi<TradingIdea[]>(
    `/api/trading-ideas/ticker/${ticker}?hours=${hours}&limit=${limit}`
  );
}

export async function getTradingIdea(id: number): Promise<TradingIdea> {
  return fetchApi<TradingIdea>(`/api/trading-ideas/${id}`);
}

// ==================== LLM ENDPOINTS ====================

export async function getLLMStatus(): Promise<LLMStatus> {
  return fetchApi<LLMStatus>("/api/llm/status");
}

export async function getLLMUsage(days: number = 30): Promise<LLMUsageResponse> {
  return fetchApi<LLMUsageResponse>(`/api/llm/usage?days=${days}`);
}

// ==================== PRICE ENDPOINTS ====================

export async function getTickerPrice(ticker: string): Promise<PriceData> {
  return fetchApi<PriceData>(`/api/prices/${ticker}`);
}

export async function getPricesBatch(tickers: string[]): Promise<PricesBatchResponse> {
  if (tickers.length === 0) {
    return { prices: {}, requested: [] };
  }
  return fetchApi<PricesBatchResponse>(`/api/prices?tickers=${tickers.join(",")}`);
}

export async function getSparkline(ticker: string, days: number = 7): Promise<SparklineData> {
  return fetchApi<SparklineData>(`/api/prices/${ticker}/sparkline?days=${days}`);
}

// ==================== CORRELATION ENDPOINTS ====================

export async function getCorrelations(
  filters: CorrelationFilters = { hours: 24 }
): Promise<CorrelationResponse> {
  const params = new URLSearchParams({
    hours: String(filters.hours),
  });

  if (filters.minMentions) params.append("min_mentions", String(filters.minMentions));
  if (filters.minSharedPeriods) params.append("min_shared_periods", String(filters.minSharedPeriods));
  if (filters.limit) params.append("limit", String(filters.limit));
  if (filters.ticker) params.append("ticker", filters.ticker);

  return fetchApi<CorrelationResponse>(`/api/correlation?${params}`);
}

export async function getCooccurrences(
  filters: CorrelationFilters = { hours: 24 }
): Promise<CooccurrenceResponse> {
  const params = new URLSearchParams({
    hours: String(filters.hours),
  });

  if (filters.minCooccurrences) params.append("min_cooccurrences", String(filters.minCooccurrences));
  if (filters.limit) params.append("limit", String(filters.limit));
  if (filters.ticker) params.append("ticker", filters.ticker);

  return fetchApi<CooccurrenceResponse>(`/api/correlation/cooccurrence?${params}`);
}

export async function getCorrelationMatrix(
  hours: number = 24,
  limit: number = 15
): Promise<CorrelationMatrixResponse> {
  return fetchApi<CorrelationMatrixResponse>(
    `/api/correlation/matrix?hours=${hours}&limit=${limit}`
  );
}

// ==================== OUTCOME TRACKING ENDPOINTS ====================

export async function recordOutcome(
  ideaId: number,
  request: OutcomeRequest
): Promise<TradingIdeaWithOutcome> {
  return fetchApi<TradingIdeaWithOutcome>(`/api/trading-ideas/${ideaId}/outcome`, {
    method: "PATCH",
    body: JSON.stringify(request),
  });
}

export async function getPerformanceStats(hours: number = 720): Promise<PerformanceStats> {
  return fetchApi<PerformanceStats>(`/api/trading-ideas/stats/performance?hours=${hours}`);
}
