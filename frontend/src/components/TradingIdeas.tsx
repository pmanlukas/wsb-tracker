import { useState } from "react";
import {
  Lightbulb,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Target,
  Shield,
  Clock,
  BarChart3,
  Filter,
  X,
  CheckCircle2,
  XCircle,
  Timer,
  Trophy,
} from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  useTradingIdeas,
  useTradingIdeasSummary,
  useLLMStatus,
} from "../hooks/useTradingIdeas";
import { recordOutcome } from "../api/client";
import { Pagination } from "./Pagination";
import type {
  TradingIdea,
  TradingIdeasFilters,
  TradeDirection,
  ConvictionLevel,
  IdeaOutcome,
  TradingIdeaWithOutcome,
} from "../types";

// Direction icon component
function DirectionIcon({ direction }: { direction: TradeDirection | null }) {
  if (direction === "bullish") {
    return <TrendingUp className="w-5 h-5 text-wsb-green" />;
  }
  if (direction === "bearish") {
    return <TrendingDown className="w-5 h-5 text-wsb-red" />;
  }
  return <Minus className="w-5 h-5 text-gray-400" />;
}

// Conviction badge component
function ConvictionBadge({ conviction }: { conviction: ConvictionLevel | null }) {
  const styles = {
    high: "bg-wsb-green/20 text-wsb-green border-wsb-green/30",
    medium: "bg-wsb-orange/20 text-wsb-orange border-wsb-orange/30",
    low: "bg-gray-600/20 text-gray-400 border-gray-600/30",
  };

  if (!conviction) return null;

  return (
    <span
      className={`px-2 py-0.5 text-xs font-medium rounded border ${styles[conviction]}`}
    >
      {conviction.toUpperCase()}
    </span>
  );
}

// Quality score bar component
function QualityBar({ score }: { score: number | null }) {
  if (score === null) return null;

  const percentage = Math.round(score * 100);
  const color =
    percentage >= 70
      ? "bg-wsb-green"
      : percentage >= 40
        ? "bg-wsb-orange"
        : "bg-gray-500";

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs text-gray-400 w-8">{percentage}%</span>
    </div>
  );
}

// Outcome badge component
function OutcomeBadge({ outcome, pnlPercent }: { outcome: IdeaOutcome; pnlPercent: number | null }) {
  const config = {
    hit_target: {
      icon: CheckCircle2,
      label: "Hit Target",
      bgColor: "bg-wsb-green/20",
      textColor: "text-wsb-green",
      borderColor: "border-wsb-green/30",
    },
    hit_stop: {
      icon: XCircle,
      label: "Hit Stop",
      bgColor: "bg-wsb-red/20",
      textColor: "text-wsb-red",
      borderColor: "border-wsb-red/30",
    },
    expired: {
      icon: Timer,
      label: "Expired",
      bgColor: "bg-gray-600/20",
      textColor: "text-gray-400",
      borderColor: "border-gray-600/30",
    },
  };

  const { icon: Icon, label, bgColor, textColor, borderColor } = config[outcome];

  return (
    <div className={`flex items-center gap-2 px-2 py-1 rounded border ${bgColor} ${borderColor}`}>
      <Icon className={`w-4 h-4 ${textColor}`} />
      <span className={`text-xs font-medium ${textColor}`}>{label}</span>
      {pnlPercent !== null && (
        <span className={`text-xs font-bold ${pnlPercent >= 0 ? "text-wsb-green" : "text-wsb-red"}`}>
          {pnlPercent >= 0 ? "+" : ""}{pnlPercent.toFixed(1)}%
        </span>
      )}
    </div>
  );
}

// Outcome recording modal
function OutcomeModal({
  idea,
  onClose,
  onSubmit,
  isLoading,
}: {
  idea: TradingIdea;
  onClose: () => void;
  onSubmit: (outcome: IdeaOutcome, price: number, notes?: string) => void;
  isLoading: boolean;
}) {
  const [outcome, setOutcome] = useState<IdeaOutcome>("hit_target");
  const [price, setPrice] = useState(
    idea.target_price?.toString() || idea.entry_price?.toString() || ""
  );
  const [notes, setNotes] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const priceNum = parseFloat(price);
    if (!isNaN(priceNum)) {
      onSubmit(outcome, priceNum, notes || undefined);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg p-6 w-full max-w-md border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Record Outcome</h3>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="mb-4 text-sm text-gray-400">
          Recording outcome for <span className="text-wsb-blue font-medium">${idea.ticker}</span>
          {idea.entry_price && (
            <span> (Entry: ${idea.entry_price.toFixed(2)})</span>
          )}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Outcome type selection */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">Outcome</label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setOutcome("hit_target")}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded border transition-colors ${
                  outcome === "hit_target"
                    ? "bg-wsb-green/20 border-wsb-green text-wsb-green"
                    : "bg-gray-700 border-gray-600 text-gray-300 hover:border-gray-500"
                }`}
              >
                <CheckCircle2 className="w-4 h-4" />
                Hit Target
              </button>
              <button
                type="button"
                onClick={() => setOutcome("hit_stop")}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded border transition-colors ${
                  outcome === "hit_stop"
                    ? "bg-wsb-red/20 border-wsb-red text-wsb-red"
                    : "bg-gray-700 border-gray-600 text-gray-300 hover:border-gray-500"
                }`}
              >
                <XCircle className="w-4 h-4" />
                Hit Stop
              </button>
              <button
                type="button"
                onClick={() => setOutcome("expired")}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded border transition-colors ${
                  outcome === "expired"
                    ? "bg-gray-600/50 border-gray-500 text-gray-300"
                    : "bg-gray-700 border-gray-600 text-gray-300 hover:border-gray-500"
                }`}
              >
                <Timer className="w-4 h-4" />
                Expired
              </button>
            </div>
          </div>

          {/* Exit price */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">Exit Price</label>
            <input
              type="number"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="Enter exit price"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-wsb-blue"
              required
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">Notes (optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add any notes about this trade..."
              rows={2}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-wsb-blue resize-none"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || !price}
              className="flex-1 px-4 py-2 bg-wsb-blue text-white rounded hover:bg-wsb-blue/80 transition-colors disabled:opacity-50"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Save Outcome"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Trading idea card component
function TradingIdeaCard({ idea }: { idea: TradingIdea | TradingIdeaWithOutcome }) {
  const [expanded, setExpanded] = useState(false);
  const [showOutcomeModal, setShowOutcomeModal] = useState(false);
  const queryClient = useQueryClient();

  // Check if idea has outcome data
  const ideaWithOutcome = idea as TradingIdeaWithOutcome;
  const hasOutcome = "outcome" in idea && ideaWithOutcome.outcome !== null;

  const outcomeMutation = useMutation({
    mutationFn: ({
      outcome,
      price,
      notes,
    }: {
      outcome: IdeaOutcome;
      price: number;
      notes?: string;
    }) =>
      recordOutcome(idea.id, {
        outcome,
        outcome_price: price,
        notes,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trading-ideas"] });
      setShowOutcomeModal(false);
    },
  });

  const handleOutcomeSubmit = (outcome: IdeaOutcome, price: number, notes?: string) => {
    outcomeMutation.mutate({ outcome, price, notes });
  };

  const redditUrl = `https://reddit.com/${idea.post_id}`;

  return (
    <>
      <div className={`card p-4 space-y-3 ${hasOutcome ? "border-l-4" : ""}`}
        style={hasOutcome ? {
          borderLeftColor: ideaWithOutcome.outcome === "hit_target" ? "var(--wsb-green, #22c55e)" :
            ideaWithOutcome.outcome === "hit_stop" ? "var(--wsb-red, #ef4444)" : "#6b7280"
        } : undefined}
      >
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <DirectionIcon direction={idea.direction} />
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-wsb-blue">
                  ${idea.ticker}
                </span>
                <ConvictionBadge conviction={idea.conviction} />
                {idea.post_type && (
                  <span className="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded">
                    {idea.post_type.toUpperCase()}
                  </span>
                )}
              </div>
              {idea.timeframe && (
                <div className="flex items-center gap-1 text-xs text-gray-500 mt-1">
                  <Clock className="w-3 h-3" />
                  {idea.timeframe}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Outcome badge or record button */}
            {hasOutcome ? (
              <OutcomeBadge
                outcome={ideaWithOutcome.outcome!}
                pnlPercent={ideaWithOutcome.outcome_pnl_percent}
              />
            ) : (
              <button
                onClick={() => setShowOutcomeModal(true)}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-colors"
                title="Record outcome"
              >
                <Trophy className="w-3 h-3" />
                Record
              </button>
            )}

            <a
              href={redditUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
              title="View on Reddit"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>

        {/* Summary */}
        {idea.summary && (
          <p className="text-sm text-gray-300">{idea.summary}</p>
        )}

        {/* Price targets */}
        {(idea.entry_price || idea.target_price || idea.stop_loss) && (
          <div className="flex flex-wrap gap-4 text-sm">
            {idea.entry_price && (
              <div className="flex items-center gap-1">
                <Target className="w-4 h-4 text-gray-500" />
                <span className="text-gray-400">Entry:</span>
                <span className="text-white font-medium">
                  ${idea.entry_price.toFixed(2)}
                </span>
              </div>
            )}
            {idea.target_price && (
              <div className="flex items-center gap-1">
                <TrendingUp className="w-4 h-4 text-wsb-green" />
                <span className="text-gray-400">Target:</span>
                <span className="text-wsb-green font-medium">
                  ${idea.target_price.toFixed(2)}
                </span>
              </div>
            )}
            {idea.stop_loss && (
              <div className="flex items-center gap-1">
                <Shield className="w-4 h-4 text-wsb-red" />
                <span className="text-gray-400">Stop:</span>
                <span className="text-wsb-red font-medium">
                  ${idea.stop_loss.toFixed(2)}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Outcome details if recorded */}
        {hasOutcome && ideaWithOutcome.outcome_price && (
          <div className="flex items-center gap-4 text-sm bg-gray-700/50 rounded px-3 py-2">
            <div className="flex items-center gap-1">
              <span className="text-gray-400">Exit:</span>
              <span className="text-white font-medium">
                ${ideaWithOutcome.outcome_price.toFixed(2)}
              </span>
            </div>
            {ideaWithOutcome.outcome_date && (
              <div className="text-gray-500 text-xs">
                {new Date(ideaWithOutcome.outcome_date).toLocaleDateString()}
              </div>
            )}
            {ideaWithOutcome.outcome_notes && (
              <div className="text-gray-400 text-xs italic flex-1 truncate" title={ideaWithOutcome.outcome_notes}>
                {ideaWithOutcome.outcome_notes}
              </div>
            )}
          </div>
        )}

        {/* Quality score */}
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-gray-500" />
          <span className="text-xs text-gray-400">Quality:</span>
          <div className="flex-1 max-w-32">
            <QualityBar score={idea.quality_score} />
          </div>
        </div>

        {/* Expandable section */}
        {(idea.key_points.length > 0 ||
          idea.catalysts.length > 0 ||
          idea.risks.length > 0) && (
          <>
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition-colors"
            >
              {expanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
              {expanded ? "Hide details" : "Show details"}
            </button>

            {expanded && (
              <div className="space-y-3 pt-2 border-t border-gray-700">
                {/* Key points */}
                {idea.key_points.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-gray-400 mb-1">
                      Key Points
                    </h4>
                    <ul className="space-y-1">
                      {idea.key_points.map((point, i) => (
                        <li
                          key={i}
                          className="text-sm text-gray-300 flex items-start gap-2"
                        >
                          <span className="text-wsb-blue mt-1">•</span>
                          {point}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Catalysts */}
                {idea.catalysts.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-gray-400 mb-1">
                      Catalysts
                    </h4>
                    <div className="flex flex-wrap gap-1">
                      {idea.catalysts.map((catalyst, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 text-xs bg-wsb-green/10 text-wsb-green rounded"
                        >
                          {catalyst}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Risks */}
                {idea.risks.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-gray-400 mb-1">
                      Risks
                    </h4>
                    <div className="flex flex-wrap gap-1">
                      {idea.risks.map((risk, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 text-xs bg-wsb-red/10 text-wsb-red rounded"
                        >
                          {risk}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Metadata */}
                <div className="text-xs text-gray-500">
                  {idea.model_used && <span>Analyzed by {idea.model_used}</span>}
                  {idea.analyzed_at && (
                    <span>
                      {" "}
                      • {new Date(idea.analyzed_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Outcome Modal */}
      {showOutcomeModal && (
        <OutcomeModal
          idea={idea}
          onClose={() => setShowOutcomeModal(false)}
          onSubmit={handleOutcomeSubmit}
          isLoading={outcomeMutation.isPending}
        />
      )}
    </>
  );
}

// Summary stats component
function SummaryStats({ hours }: { hours: number }) {
  const { data: summary, isLoading } = useTradingIdeasSummary(hours);

  if (isLoading || !summary) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="card p-4 animate-pulse">
            <div className="h-4 bg-gray-700 rounded w-20 mb-2" />
            <div className="h-8 bg-gray-700 rounded w-12" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div className="card p-4">
        <div className="text-sm text-gray-400">Total Ideas</div>
        <div className="text-2xl font-bold text-white">{summary.total_ideas}</div>
        <div className="text-xs text-gray-500">
          {summary.actionable_count} actionable
        </div>
      </div>

      <div className="card p-4">
        <div className="text-sm text-gray-400">Bullish / Bearish</div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-wsb-green">
            {summary.bullish_count}
          </span>
          <span className="text-gray-500">/</span>
          <span className="text-2xl font-bold text-wsb-red">
            {summary.bearish_count}
          </span>
        </div>
        <div className="text-xs text-gray-500">
          {summary.neutral_count} neutral
        </div>
      </div>

      <div className="card p-4">
        <div className="text-sm text-gray-400">High Conviction</div>
        <div className="text-2xl font-bold text-wsb-orange">
          {summary.high_conviction_count}
        </div>
        <div className="text-xs text-gray-500">
          {summary.total_ideas > 0
            ? Math.round((summary.high_conviction_count / summary.total_ideas) * 100)
            : 0}
          % of total
        </div>
      </div>

      <div className="card p-4">
        <div className="text-sm text-gray-400">Avg Quality</div>
        <div className="text-2xl font-bold text-white">
          {(summary.avg_quality * 100).toFixed(0)}%
        </div>
        <QualityBar score={summary.avg_quality} />
      </div>
    </div>
  );
}

// LLM status banner component
function LLMStatusBanner() {
  const { data: status, isLoading } = useLLMStatus();

  if (isLoading) return null;

  if (!status?.enabled || !status?.has_credentials) {
    return (
      <div className="card p-4 bg-wsb-orange/10 border border-wsb-orange/30">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-wsb-orange mt-0.5" />
          <div>
            <h4 className="font-medium text-wsb-orange">LLM Analysis Disabled</h4>
            <p className="text-sm text-gray-400 mt-1">
              {!status?.enabled
                ? "LLM analysis is disabled in configuration. Set WSB_LLM_ENABLED=true to enable."
                : "ANTHROPIC_API_KEY not configured. Add your API key to enable AI-powered trading idea extraction."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (status.daily_limit_reached) {
    return (
      <div className="card p-4 bg-wsb-red/10 border border-wsb-red/30">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-wsb-red mt-0.5" />
          <div>
            <h4 className="font-medium text-wsb-red">Daily Limit Reached</h4>
            <p className="text-sm text-gray-400 mt-1">
              Daily LLM call limit of {status.max_daily_calls} has been reached.
              Analysis will resume tomorrow.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-4 bg-gray-800">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 bg-wsb-green rounded-full animate-pulse" />
          <span className="text-sm text-gray-300">
            LLM Analysis Active ({status.model})
          </span>
        </div>
        <div className="text-sm text-gray-400">
          {status.today_calls} / {status.max_daily_calls} calls today
          <span className="text-gray-500 ml-2">
            (${status.today_cost.toFixed(2)})
          </span>
        </div>
      </div>
    </div>
  );
}

// Main component
export function TradingIdeas() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [filters, setFilters] = useState<TradingIdeasFilters>({
    hours: 24,
  });
  const [showFilters, setShowFilters] = useState(false);

  const { data, isLoading, error } = useTradingIdeas(page, pageSize, filters);

  // Filter handlers
  const updateFilter = <K extends keyof TradingIdeasFilters>(
    key: K,
    value: TradingIdeasFilters[K]
  ) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1); // Reset to first page
  };

  const clearFilters = () => {
    setFilters({ hours: 24 });
    setPage(1);
  };

  const hasActiveFilters =
    filters.ticker ||
    filters.direction ||
    filters.conviction ||
    filters.postType ||
    filters.minQuality !== undefined ||
    filters.actionableOnly;

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-12 h-12 text-wsb-red mx-auto mb-4" />
        <p className="text-wsb-red">Failed to load trading ideas</p>
        <p className="text-gray-500 text-sm mt-2">
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Lightbulb className="w-6 h-6 text-wsb-orange" />
          <h2 className="text-xl font-semibold text-white">Trading Ideas</h2>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={filters.hours || 24}
            onChange={(e) => updateFilter("hours", Number(e.target.value))}
            className="bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-wsb-blue"
          >
            <option value={6}>Last 6 hours</option>
            <option value={24}>Last 24 hours</option>
            <option value={48}>Last 48 hours</option>
            <option value={168}>Last 7 days</option>
          </select>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded transition-colors ${
              showFilters || hasActiveFilters
                ? "bg-wsb-blue text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
          >
            <Filter className="w-4 h-4" />
            Filters
            {hasActiveFilters && (
              <span className="w-2 h-2 bg-wsb-orange rounded-full" />
            )}
          </button>
        </div>
      </div>

      {/* LLM Status */}
      <LLMStatusBanner />

      {/* Summary Stats */}
      <SummaryStats hours={filters.hours || 24} />

      {/* Filters panel */}
      {showFilters && (
        <div className="card p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-300">Filters</h3>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="flex items-center gap-1 text-sm text-gray-400 hover:text-white"
              >
                <X className="w-4 h-4" />
                Clear all
              </button>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Ticker</label>
              <input
                type="text"
                value={filters.ticker || ""}
                onChange={(e) =>
                  updateFilter("ticker", e.target.value.toUpperCase() || undefined)
                }
                placeholder="Any"
                className="w-full px-3 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-wsb-blue"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Direction</label>
              <select
                value={filters.direction || ""}
                onChange={(e) =>
                  updateFilter(
                    "direction",
                    (e.target.value as TradeDirection) || undefined
                  )
                }
                className="w-full px-3 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-wsb-blue"
              >
                <option value="">Any</option>
                <option value="bullish">Bullish</option>
                <option value="bearish">Bearish</option>
                <option value="neutral">Neutral</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Conviction</label>
              <select
                value={filters.conviction || ""}
                onChange={(e) =>
                  updateFilter(
                    "conviction",
                    (e.target.value as ConvictionLevel) || undefined
                  )
                }
                className="w-full px-3 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-wsb-blue"
              >
                <option value="">Any</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Min Quality</label>
              <select
                value={filters.minQuality !== undefined ? String(filters.minQuality) : ""}
                onChange={(e) =>
                  updateFilter(
                    "minQuality",
                    e.target.value ? Number(e.target.value) : undefined
                  )
                }
                className="w-full px-3 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-wsb-blue"
              >
                <option value="">Any</option>
                <option value="0.3">30%+</option>
                <option value="0.5">50%+</option>
                <option value="0.7">70%+</option>
                <option value="0.8">80%+</option>
              </select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filters.actionableOnly || false}
                  onChange={(e) => updateFilter("actionableOnly", e.target.checked || undefined)}
                  className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-wsb-blue focus:ring-wsb-blue"
                />
                <span className="text-sm text-gray-300">Actionable only</span>
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Ideas list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-wsb-blue" />
        </div>
      ) : !data?.ideas.length ? (
        <div className="text-center py-12">
          <Lightbulb className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">No trading ideas found</p>
          <p className="text-gray-500 text-sm mt-2">
            {hasActiveFilters
              ? "Try adjusting your filters"
              : "Run a scan to analyze posts and extract trading ideas"}
          </p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            {data.ideas.map((idea) => (
              <TradingIdeaCard key={idea.id} idea={idea} />
            ))}
          </div>

          {/* Pagination */}
          {data.total_pages > 1 && (
            <Pagination
              page={page}
              totalPages={data.total_pages}
              pageSize={pageSize}
              total={data.total}
              onPageChange={setPage}
              onPageSizeChange={(newSize) => {
                setPageSize(newSize);
                setPage(1);
              }}
            />
          )}
        </>
      )}
    </div>
  );
}
