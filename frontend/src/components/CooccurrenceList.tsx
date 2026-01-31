import { Link2 } from "lucide-react";
import type { TickerCooccurrence } from "../types";

interface CooccurrenceListProps {
  cooccurrences: TickerCooccurrence[];
  onTickerClick?: (ticker: string) => void;
}

/**
 * Get sentiment color class
 */
function getSentimentColor(sentiment: number): string {
  if (sentiment >= 0.25) return "text-green-600";
  if (sentiment <= -0.25) return "text-red-600";
  return "text-gray-600";
}

/**
 * Get sentiment background color
 */
function getSentimentBgColor(sentiment: number): string {
  if (sentiment >= 0.25) return "bg-green-50";
  if (sentiment <= -0.25) return "bg-red-50";
  return "bg-gray-50";
}

export function CooccurrenceList({
  cooccurrences,
  onTickerClick,
}: CooccurrenceListProps) {
  if (cooccurrences.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        No co-occurrence data available
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {cooccurrences.map((pair, idx) => (
        <div
          key={`${pair.ticker_a}-${pair.ticker_b}`}
          className={`p-3 rounded-lg border ${getSentimentBgColor(pair.avg_combined_sentiment)}`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-gray-400 text-sm w-6">{idx + 1}.</span>
              <button
                onClick={() => onTickerClick?.(pair.ticker_a)}
                className="font-semibold text-blue-600 hover:underline"
              >
                {pair.ticker_a}
              </button>
              <Link2 className="w-4 h-4 text-gray-400" />
              <button
                onClick={() => onTickerClick?.(pair.ticker_b)}
                className="font-semibold text-blue-600 hover:underline"
              >
                {pair.ticker_b}
              </button>
            </div>

            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-sm text-gray-500">Mentioned together</div>
                <div className="font-semibold">
                  {pair.cooccurrence_count} times
                </div>
              </div>

              <div className="text-right min-w-[100px]">
                <div className="text-sm text-gray-500">Combined Sentiment</div>
                <div
                  className={`font-semibold ${getSentimentColor(pair.avg_combined_sentiment)}`}
                >
                  {pair.avg_combined_sentiment >= 0 ? "+" : ""}
                  {pair.avg_combined_sentiment.toFixed(2)}
                </div>
              </div>
            </div>
          </div>

          {pair.sample_post_ids.length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-200">
              <div className="text-xs text-gray-500">
                Sample posts:{" "}
                {pair.sample_post_ids.slice(0, 3).map((postId, postIdx) => (
                  <span key={postId}>
                    {postIdx > 0 && ", "}
                    <a
                      href={`https://reddit.com/${postId}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-500 hover:underline"
                    >
                      {postId}
                    </a>
                  </span>
                ))}
                {pair.sample_post_ids.length > 3 && (
                  <span> +{pair.sample_post_ids.length - 3} more</span>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
