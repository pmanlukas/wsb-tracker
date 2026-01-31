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

// ==================== MENTION EXPLORER TYPES ====================

export interface MentionDetail {
  id: number;
  ticker: string;
  post_id: string;
  post_title: string;
  subreddit: string;
  sentiment_compound: number;
  sentiment_label: string;
  context: string;
  post_score: number;
  post_flair: string | null;
  is_dd_post: boolean;
  timestamp: string;
}

export interface MentionsListResponse {
  mentions: MentionDetail[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface MentionFilters {
  ticker?: string;
  subreddit?: string;
  dateFrom?: string;
  dateTo?: string;
  sentimentMin?: number;
  sentimentMax?: number;
  sortBy: string;
  sortOrder: "asc" | "desc";
}

export interface FilterOptions {
  tickers: string[];
  subreddits: string[];
}

// ==================== SETTINGS TYPES ====================

export interface ScanSettings {
  subreddits: string[];
  scan_limit: number;
  request_delay: number;
  min_score: number;
  scan_sort: "hot" | "new" | "rising" | "top";
  available_sorts: string[];
}

export interface ScanSettingsUpdate {
  subreddits: string[];
  scan_limit: number;
  request_delay: number;
  min_score: number;
  scan_sort: string;
}

// ==================== TRADING IDEAS TYPES ====================

export type TradeDirection = "bullish" | "bearish" | "neutral";
export type ConvictionLevel = "high" | "medium" | "low";
export type PostType = "dd" | "yolo" | "gain_loss" | "meme" | "news" | "discussion" | "question" | "other";
export type Timeframe = "intraday" | "swing" | "weeks" | "months" | "long_term";

export interface TradingIdea {
  id: number;
  ticker: string;
  post_id: string;
  mention_id?: number | null;
  has_actionable_idea: boolean;
  direction: TradeDirection | null;
  conviction: ConvictionLevel | null;
  timeframe: Timeframe | null;
  entry_price: number | null;
  target_price: number | null;
  stop_loss: number | null;
  catalysts: string[];
  risks: string[];
  key_points: string[];
  post_type: PostType | null;
  quality_score: number | null;
  summary: string | null;
  model_used: string | null;
  analyzed_at: string | null;
}

export interface TradingIdeasListResponse {
  ideas: TradingIdea[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TradingIdeasSummary {
  total_ideas: number;
  actionable_count: number;
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  high_conviction_count: number;
  avg_quality: number;
}

export interface TradingIdeasFilters {
  ticker?: string;
  direction?: TradeDirection;
  conviction?: ConvictionLevel;
  postType?: PostType;
  minQuality?: number;
  actionableOnly?: boolean;
  hours?: number;
}

export interface TradingIdeasFilterOptions {
  directions: TradeDirection[];
  convictions: ConvictionLevel[];
  post_types: PostType[];
  timeframes: Timeframe[];
}

// ==================== LLM TYPES ====================

export interface LLMStatus {
  enabled: boolean;
  has_credentials: boolean;
  model: string;
  min_post_score: number;
  analyze_dd_only: boolean;
  max_daily_calls: number;
  today_calls: number;
  today_cost: number;
  daily_limit_reached: boolean;
}

export interface LLMUsageDay {
  date: string;
  provider: string;
  model: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost_usd: number;
}

export interface LLMUsageResponse {
  today: {
    date: string;
    calls: number;
    prompt_tokens: number;
    completion_tokens: number;
    estimated_cost_usd: number;
  };
  period_summary: {
    period_days: number;
    active_days: number;
    total_calls: number;
    total_prompt_tokens: number;
    total_completion_tokens: number;
    total_cost_usd: number;
    avg_daily_cost: number;
  };
  daily_usage: LLMUsageDay[];
}

// ==================== PRICE TYPES ====================

export interface PriceData {
  ticker: string;
  current_price: number | null;
  change_percent: number | null;
  change_amount: number | null;
  volume: number | null;
  market_cap: number | null;
  day_high: number | null;
  day_low: number | null;
  prev_close: number | null;
  updated_at: string;
  error?: string;
}

export interface PricesBatchResponse {
  prices: Record<string, PriceData>;
  requested: string[];
}

export interface SparklineData {
  ticker: string;
  prices: number[];
  days: number;
  updated_at: string;
}

// ==================== CORRELATION TYPES ====================

export interface TickerCorrelation {
  ticker_a: string;
  ticker_b: string;
  correlation: number;
  shared_periods: number;
  avg_sentiment_a: number;
  avg_sentiment_b: number;
}

export interface TickerCooccurrence {
  ticker_a: string;
  ticker_b: string;
  cooccurrence_count: number;
  avg_combined_sentiment: number;
  sample_post_ids: string[];
}

export interface CorrelationResponse {
  correlations: TickerCorrelation[];
  hours: number;
  generated_at: string;
}

export interface CooccurrenceResponse {
  cooccurrences: TickerCooccurrence[];
  hours: number;
  generated_at: string;
}

export interface CorrelationMatrixResponse {
  tickers: string[];
  matrix: number[][];
  hours: number;
  generated_at: string;
}

export interface CorrelationFilters {
  hours: number;
  minMentions?: number;
  minSharedPeriods?: number;
  minCooccurrences?: number;
  limit?: number;
  ticker?: string;
}

// ==================== OUTCOME TRACKING TYPES ====================

export type IdeaOutcome = "hit_target" | "hit_stop" | "expired";

export interface TradingIdeaWithOutcome extends TradingIdea {
  outcome: IdeaOutcome | null;
  outcome_price: number | null;
  outcome_date: string | null;
  outcome_pnl_percent: number | null;
  outcome_notes: string | null;
}

export interface OutcomeRequest {
  outcome: IdeaOutcome;
  outcome_price: number;
  notes?: string;
}

export interface PerformanceStats {
  total_ideas: number;
  outcomes_recorded: number;
  hit_target_count: number;
  hit_stop_count: number;
  expired_count: number;
  win_rate: number;
  win_rate_by_direction: Record<string, number>;
  win_rate_by_conviction: Record<string, number>;
  avg_pnl_percent: number;
}
