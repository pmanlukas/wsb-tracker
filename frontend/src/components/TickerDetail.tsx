import { TrendingUp, TrendingDown, Minus, ExternalLink, X } from "lucide-react";
import { useTickerDetail } from "../hooks/useTickers";
import { TickerChart } from "./TickerChart";
import type { Ticker } from "../types";

interface TickerDetailProps {
  ticker: Ticker;
  hours: number;
  onClose: () => void;
}

export function TickerDetail({ ticker, hours, onClose }: TickerDetailProps) {
  const { data, isLoading, error } = useTickerDetail(ticker.ticker, hours);

  const getSentimentIcon = (label: string) => {
    switch (label) {
      case "bullish":
      case "very_bullish":
        return <TrendingUp className="w-5 h-5 text-wsb-green" />;
      case "bearish":
      case "very_bearish":
        return <TrendingDown className="w-5 h-5 text-wsb-red" />;
      default:
        return <Minus className="w-5 h-5 text-gray-400" />;
    }
  };

  const getHeatClass = (score: number): string => {
    if (score >= 7) return "text-wsb-red";
    if (score >= 4) return "text-wsb-orange";
    return "text-wsb-green";
  };

  const getSentimentClass = (label: string): string => {
    if (label.includes("bullish")) return "text-wsb-green";
    if (label.includes("bearish")) return "text-wsb-red";
    return "text-gray-400";
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-gray-800 border-b border-gray-700 p-4 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold text-wsb-blue">
                {ticker.ticker}
              </h2>
              {ticker.type && (
                <span className="text-xs px-2 py-1 bg-gray-700 rounded">
                  {ticker.type}
                </span>
              )}
              <a
                href={`https://finance.yahoo.com/quote/${ticker.ticker}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-400 hover:text-wsb-blue"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
            {ticker.name && (
              <p className="text-gray-400 mt-1">{ticker.name}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-6">
          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-gray-700/50 p-3 rounded-lg">
              <div className="text-xs text-gray-400">Heat Score</div>
              <div className={`text-2xl font-bold ${getHeatClass(ticker.heat_score)}`}>
                {ticker.heat_score.toFixed(1)}
              </div>
            </div>
            <div className="bg-gray-700/50 p-3 rounded-lg">
              <div className="text-xs text-gray-400">Mentions</div>
              <div className="text-2xl font-bold">{ticker.mention_count}</div>
            </div>
            <div className="bg-gray-700/50 p-3 rounded-lg">
              <div className="text-xs text-gray-400">Sentiment</div>
              <div className="flex items-center gap-2">
                {getSentimentIcon(ticker.sentiment_label)}
                <span className={`text-xl font-bold ${getSentimentClass(ticker.sentiment_label)}`}>
                  {ticker.avg_sentiment.toFixed(2)}
                </span>
              </div>
            </div>
            <div className="bg-gray-700/50 p-3 rounded-lg">
              <div className="text-xs text-gray-400">DD Posts</div>
              <div className="text-2xl font-bold text-wsb-orange">
                {ticker.dd_count}
              </div>
            </div>
          </div>

          {/* Trend */}
          {ticker.trend_pct !== null && (
            <div className="bg-gray-700/50 p-3 rounded-lg">
              <div className="text-xs text-gray-400 mb-1">24h Trend</div>
              <div
                className={`text-lg font-bold ${
                  ticker.trend_pct > 0
                    ? "text-wsb-green"
                    : ticker.trend_pct < 0
                    ? "text-wsb-red"
                    : "text-gray-400"
                }`}
              >
                {ticker.trend_pct > 0 ? "+" : ""}
                {ticker.trend_pct.toFixed(0)}% mention change
              </div>
            </div>
          )}

          {/* Charts */}
          {isLoading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-48 bg-gray-700 rounded"></div>
              <div className="h-36 bg-gray-700 rounded"></div>
            </div>
          ) : error ? (
            <div className="text-center py-8 text-wsb-red">
              Failed to load detail data
            </div>
          ) : data?.recent_mentions && data.recent_mentions.length > 0 ? (
            <TickerChart
              mentions={data.recent_mentions}
              ticker={ticker.ticker}
            />
          ) : (
            <div className="text-center py-8 text-gray-500">
              No mention data available for charts
            </div>
          )}

          {/* Recent Mentions */}
          {data?.recent_mentions && data.recent_mentions.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-400 mb-3">
                Recent Mentions
              </h4>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {data.recent_mentions.slice(0, 10).map((mention, index) => (
                  <div
                    key={`${mention.post_id}-${index}`}
                    className="bg-gray-700/50 p-3 rounded-lg"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{mention.post_title}</p>
                        <p className="text-xs text-gray-400 mt-1 line-clamp-2">{mention.context}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className={`text-xs ${getSentimentClass(mention.sentiment_label)}`}>
                            {mention.sentiment.toFixed(2)} ({mention.sentiment_label})
                          </span>
                          {mention.is_dd && (
                            <span className="text-xs px-1.5 py-0.5 bg-wsb-orange/20 text-wsb-orange rounded">
                              DD
                            </span>
                          )}
                          <span className="text-xs text-gray-500">
                            r/{mention.subreddit}
                          </span>
                          <span className="text-xs text-gray-500">
                            {new Date(mention.timestamp).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-700 p-4">
          <button onClick={onClose} className="w-full btn btn-primary">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
