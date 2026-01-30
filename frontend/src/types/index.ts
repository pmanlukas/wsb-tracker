// Ticker types
export interface Ticker {
  ticker: string;
  name: string | null;
  type: string | null;
  heat_score: number;
  mention_count: number;
  avg_sentiment: number;
  sentiment_label: string;
  trend_pct: number | null;
  dd_count: number;
}

export interface TickersResponse {
  tickers: Ticker[];
  hours: number;
  updated_at: string;
}

export interface Mention {
  post_id: string;
  post_title: string;
  context: string;
  sentiment: number;
  sentiment_label: string;
  timestamp: string;
  subreddit: string;
  post_score: number;
  is_dd: boolean;
}

export interface TickerDetailResponse {
  ticker: string;
  name: string;
  type: string;
  summary: Ticker;
  recent_mentions: Mention[];
}

// Scan types
export interface Snapshot {
  id: number;
  scan_time: string;
  post_count: number;
  ticker_count: number;
  top_ticker: string | null;
  top_heat: number | null;
}

export interface SnapshotsResponse {
  snapshots: Snapshot[];
}

export interface ScanStatus {
  scan_id: string;
  status: "pending" | "running" | "complete" | "error";
  progress?: {
    posts: number;
    tickers: number;
  };
  error?: string;
}

export interface ScanStartResponse {
  scan_id: string;
  status: string;
  message: string;
}

// Alert types
export interface Alert {
  id: number;
  ticker: string;
  alert_type: string;
  message: string;
  heat_score: number;
  triggered_at: string;
  acknowledged: boolean;
}

export interface AlertsResponse {
  alerts: Alert[];
  total: number;
  unacknowledged: number;
}

// Stats types (returned directly, not nested)
export interface StatsResponse {
  total_mentions: number;
  total_snapshots: number;
  unique_tickers: number;
  total_posts: number;
  total_alerts: number;
  unacknowledged_alerts: number;
  database_size_mb: number;
  oldest_mention: string | null;
  newest_mention: string | null;
}

// WebSocket types
export type WebSocketEventType =
  | "connected"
  | "scan_started"
  | "scan_progress"
  | "scan_complete"
  | "scan_error"
  | "new_alert";

export interface WebSocketEvent<T = unknown> {
  event: WebSocketEventType;
  data: T;
}

export interface ScanProgressData {
  scan_id: string;
  posts: number;
  tickers: number;
}

export interface ScanCompleteData {
  scan_id: string;
  duration: number;
  posts: number;
  tickers: number;
}

export interface NewAlertData {
  ticker: string;
  type: string;
  heat_score: number;
  message: string;
}
