import { useState, useMemo } from "react";
import { TrendingUp, TrendingDown, Minus, ChevronUp, ChevronDown, DollarSign } from "lucide-react";
import type { Ticker } from "../types";
import { usePrices } from "../hooks/usePrices";

interface TickerTableProps {
  tickers: Ticker[];
  onTickerClick?: (ticker: Ticker) => void;
}

type SortField = "ticker" | "heat_score" | "mention_count" | "avg_sentiment" | "trend_pct" | "price" | "price_change";
type SortDirection = "asc" | "desc";

export function TickerTable({ tickers, onTickerClick }: TickerTableProps) {
  const [sortField, setSortField] = useState<SortField>("heat_score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  // Get all ticker symbols for price fetching
  const tickerSymbols = useMemo(() => tickers.map((t) => t.ticker), [tickers]);
  const { data: pricesData, isLoading: pricesLoading } = usePrices(tickerSymbols);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const sortedTickers = useMemo(() => {
    return [...tickers].sort((a, b) => {
      let aVal: number | string | null;
      let bVal: number | string | null;

      // Handle price-based sorting
      if (sortField === "price") {
        aVal = pricesData?.prices[a.ticker]?.current_price ?? null;
        bVal = pricesData?.prices[b.ticker]?.current_price ?? null;
      } else if (sortField === "price_change") {
        aVal = pricesData?.prices[a.ticker]?.change_percent ?? null;
        bVal = pricesData?.prices[b.ticker]?.change_percent ?? null;
      } else {
        aVal = a[sortField];
        bVal = b[sortField];
      }

      // Handle null values
      if (aVal === null) aVal = sortDirection === "asc" ? Infinity : -Infinity;
      if (bVal === null) bVal = sortDirection === "asc" ? Infinity : -Infinity;

      if (typeof aVal === "string") {
        return sortDirection === "asc"
          ? aVal.localeCompare(bVal as string)
          : (bVal as string).localeCompare(aVal);
      }

      return sortDirection === "asc"
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });
  }, [tickers, sortField, sortDirection, pricesData]);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return sortDirection === "asc" ? (
      <ChevronUp className="inline w-4 h-4" />
    ) : (
      <ChevronDown className="inline w-4 h-4" />
    );
  };

  const getHeatClass = (score: number): string => {
    if (score >= 7) return "heat-high";
    if (score >= 4) return "heat-medium";
    return "heat-low";
  };

  const getSentimentIcon = (label: string) => {
    switch (label) {
      case "bullish":
        return <TrendingUp className="w-4 h-4 text-wsb-green" />;
      case "bearish":
        return <TrendingDown className="w-4 h-4 text-wsb-red" />;
      default:
        return <Minus className="w-4 h-4 text-gray-400" />;
    }
  };

  const formatTrend = (trend: number | null): string => {
    if (trend === null) return "N/A";
    const sign = trend > 0 ? "+" : "";
    return `${sign}${trend.toFixed(0)}%`;
  };

  const getTrendClass = (trend: number | null): string => {
    if (trend === null) return "text-gray-500";
    if (trend > 50) return "text-wsb-green";
    if (trend < -50) return "text-wsb-red";
    return "text-gray-400";
  };

  const formatPrice = (price: number | null | undefined): string => {
    if (price === null || price === undefined) return "—";
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const formatPriceChange = (change: number | null | undefined): string => {
    if (change === null || change === undefined) return "—";
    const sign = change > 0 ? "+" : "";
    return `${sign}${change.toFixed(2)}%`;
  };

  const getPriceChangeClass = (change: number | null | undefined): string => {
    if (change === null || change === undefined) return "text-gray-500";
    if (change > 0) return "text-wsb-green";
    if (change < 0) return "text-wsb-red";
    return "text-gray-400";
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700 text-gray-400">
            <th
              className="px-4 py-3 text-left cursor-pointer hover:text-white"
              onClick={() => handleSort("ticker")}
            >
              Ticker <SortIcon field="ticker" />
            </th>
            <th className="px-4 py-3 text-left">Name</th>
            <th
              className="px-4 py-3 text-right cursor-pointer hover:text-white"
              onClick={() => handleSort("price")}
            >
              <span className="flex items-center justify-end gap-1">
                <DollarSign className="w-3 h-3" />
                Price <SortIcon field="price" />
              </span>
            </th>
            <th
              className="px-4 py-3 text-right cursor-pointer hover:text-white"
              onClick={() => handleSort("price_change")}
            >
              Change <SortIcon field="price_change" />
            </th>
            <th
              className="px-4 py-3 text-right cursor-pointer hover:text-white"
              onClick={() => handleSort("heat_score")}
            >
              Heat <SortIcon field="heat_score" />
            </th>
            <th
              className="px-4 py-3 text-right cursor-pointer hover:text-white"
              onClick={() => handleSort("mention_count")}
            >
              Mentions <SortIcon field="mention_count" />
            </th>
            <th
              className="px-4 py-3 text-center cursor-pointer hover:text-white"
              onClick={() => handleSort("avg_sentiment")}
            >
              Sentiment <SortIcon field="avg_sentiment" />
            </th>
            <th
              className="px-4 py-3 text-right cursor-pointer hover:text-white"
              onClick={() => handleSort("trend_pct")}
            >
              Trend <SortIcon field="trend_pct" />
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedTickers.map((ticker) => {
            const priceData = pricesData?.prices[ticker.ticker];
            return (
              <tr
                key={ticker.ticker}
                className="border-b border-gray-700/50 hover:bg-gray-800/50 cursor-pointer transition-colors"
                onClick={() => onTickerClick?.(ticker)}
              >
                <td className="px-4 py-3 font-mono font-bold text-wsb-blue">
                  {ticker.ticker}
                </td>
                <td className="px-4 py-3 text-gray-300 max-w-[150px] truncate">
                  {ticker.name || "—"}
                </td>
                <td className="px-4 py-3 text-right text-gray-300 font-mono">
                  {pricesLoading ? (
                    <span className="text-gray-500">...</span>
                  ) : (
                    formatPrice(priceData?.current_price)
                  )}
                </td>
                <td className={`px-4 py-3 text-right font-mono ${getPriceChangeClass(priceData?.change_percent)}`}>
                  {pricesLoading ? (
                    <span className="text-gray-500">...</span>
                  ) : (
                    formatPriceChange(priceData?.change_percent)
                  )}
                </td>
                <td className={`px-4 py-3 text-right ${getHeatClass(ticker.heat_score)}`}>
                  {ticker.heat_score.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-right text-gray-300">
                  {ticker.mention_count}
                  {ticker.dd_count > 0 && (
                    <span className="ml-1 text-xs text-wsb-orange">
                      ({ticker.dd_count} DD)
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-center gap-2">
                    {getSentimentIcon(ticker.sentiment_label)}
                    <span
                      className={`text-xs ${
                        ticker.sentiment_label === "bullish"
                          ? "text-wsb-green"
                          : ticker.sentiment_label === "bearish"
                          ? "text-wsb-red"
                          : "text-gray-400"
                      }`}
                    >
                      {ticker.avg_sentiment.toFixed(2)}
                    </span>
                  </div>
                </td>
                <td className={`px-4 py-3 text-right ${getTrendClass(ticker.trend_pct)}`}>
                  {formatTrend(ticker.trend_pct)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {tickers.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          No tickers found. Run a scan to collect data.
        </div>
      )}
    </div>
  );
}
