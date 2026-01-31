import { useState } from "react";
import { GitCompare, Link2, Grid3X3, RefreshCw, Info } from "lucide-react";
import { CorrelationHeatmap } from "./CorrelationHeatmap";
import { CooccurrenceList } from "./CooccurrenceList";
import {
  useCorrelationMatrix,
  useCooccurrences,
  useCorrelations,
} from "../hooks/useCorrelation";

type ViewMode = "heatmap" | "cooccurrence" | "pairs";

interface CorrelationAnalysisProps {
  onTickerSelect?: (ticker: string) => void;
}

export function CorrelationAnalysis({
  onTickerSelect,
}: CorrelationAnalysisProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("heatmap");
  const [hours, setHours] = useState(24);
  const [matrixLimit, setMatrixLimit] = useState(15);

  // Fetch data based on view mode
  const {
    data: matrixData,
    isLoading: matrixLoading,
    refetch: refetchMatrix,
  } = useCorrelationMatrix(hours, matrixLimit);

  const {
    data: cooccurrenceData,
    isLoading: cooccurrenceLoading,
    refetch: refetchCooccurrence,
  } = useCooccurrences({ hours, limit: 50 });

  const {
    data: pairsData,
    isLoading: pairsLoading,
    refetch: refetchPairs,
  } = useCorrelations({ hours, limit: 50 });

  const handleRefresh = () => {
    if (viewMode === "heatmap") refetchMatrix();
    else if (viewMode === "cooccurrence") refetchCooccurrence();
    else refetchPairs();
  };

  const isLoading =
    (viewMode === "heatmap" && matrixLoading) ||
    (viewMode === "cooccurrence" && cooccurrenceLoading) ||
    (viewMode === "pairs" && pairsLoading);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitCompare className="w-6 h-6 text-blue-600" />
          <h2 className="text-xl font-semibold">Correlation Analysis</h2>
        </div>

        <button
          onClick={handleRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Info box */}
      <div className="flex items-start gap-3 p-4 bg-blue-50 rounded-lg text-sm">
        <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-blue-900">
            Understanding Sentiment Correlations
          </p>
          <p className="text-blue-700 mt-1">
            <strong>Positive correlation (+1):</strong> Sentiments move together
            - when one ticker is bullish, the other tends to be bullish too.
            <br />
            <strong>Negative correlation (-1):</strong> Sentiments move
            oppositely - when one is bullish, the other tends to be bearish.
            <br />
            <strong>No correlation (0):</strong> Sentiments are independent.
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        {/* View mode tabs */}
        <div className="flex rounded-lg overflow-hidden border border-gray-200">
          <button
            onClick={() => setViewMode("heatmap")}
            className={`flex items-center gap-2 px-4 py-2 text-sm ${
              viewMode === "heatmap"
                ? "bg-blue-600 text-white"
                : "bg-white hover:bg-gray-50"
            }`}
          >
            <Grid3X3 className="w-4 h-4" />
            Heatmap
          </button>
          <button
            onClick={() => setViewMode("cooccurrence")}
            className={`flex items-center gap-2 px-4 py-2 text-sm border-l ${
              viewMode === "cooccurrence"
                ? "bg-blue-600 text-white"
                : "bg-white hover:bg-gray-50"
            }`}
          >
            <Link2 className="w-4 h-4" />
            Co-occurrence
          </button>
          <button
            onClick={() => setViewMode("pairs")}
            className={`flex items-center gap-2 px-4 py-2 text-sm border-l ${
              viewMode === "pairs"
                ? "bg-blue-600 text-white"
                : "bg-white hover:bg-gray-50"
            }`}
          >
            <GitCompare className="w-4 h-4" />
            Pairs
          </button>
        </div>

        {/* Time period selector */}
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Time period:</label>
          <select
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            className="px-3 py-2 border rounded-lg text-sm"
          >
            <option value={6}>6 hours</option>
            <option value={12}>12 hours</option>
            <option value={24}>24 hours</option>
            <option value={48}>48 hours</option>
            <option value={72}>3 days</option>
            <option value={168}>7 days</option>
            <option value={720}>30 days</option>
          </select>
        </div>

        {/* Matrix size selector (only for heatmap) */}
        {viewMode === "heatmap" && (
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">Top tickers:</label>
            <select
              value={matrixLimit}
              onChange={(e) => setMatrixLimit(Number(e.target.value))}
              className="px-3 py-2 border rounded-lg text-sm"
            >
              <option value={10}>10</option>
              <option value={15}>15</option>
              <option value={20}>20</option>
              <option value={25}>25</option>
              <option value={30}>30</option>
            </select>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="bg-white rounded-lg border p-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : viewMode === "heatmap" && matrixData ? (
          <CorrelationHeatmap
            data={matrixData}
            onCellClick={(tickerA, tickerB, correlation) => {
              console.log(`Clicked: ${tickerA} vs ${tickerB} = ${correlation}`);
            }}
          />
        ) : viewMode === "cooccurrence" && cooccurrenceData ? (
          <CooccurrenceList
            cooccurrences={cooccurrenceData.cooccurrences}
            onTickerClick={onTickerSelect}
          />
        ) : viewMode === "pairs" && pairsData ? (
          <CorrelationPairsList
            correlations={pairsData.correlations}
            onTickerClick={onTickerSelect}
          />
        ) : (
          <div className="text-center text-gray-500 py-12">
            No data available for the selected time period
          </div>
        )}
      </div>

      {/* Generated timestamp */}
      {matrixData && viewMode === "heatmap" && (
        <div className="text-xs text-gray-500 text-right">
          Generated at:{" "}
          {new Date(matrixData.generated_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}

// Sub-component for correlation pairs list
import type { TickerCorrelation } from "../types";

interface CorrelationPairsListProps {
  correlations: TickerCorrelation[];
  onTickerClick?: (ticker: string) => void;
}

function CorrelationPairsList({
  correlations,
  onTickerClick,
}: CorrelationPairsListProps) {
  if (correlations.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        No correlation data available
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {correlations.map((pair, idx) => {
        const isPositive = pair.correlation > 0;
        const absCorrelation = Math.abs(pair.correlation);
        const strength =
          absCorrelation > 0.7
            ? "Strong"
            : absCorrelation > 0.4
              ? "Moderate"
              : "Weak";

        return (
          <div
            key={`${pair.ticker_a}-${pair.ticker_b}`}
            className={`p-3 rounded-lg border ${
              isPositive ? "bg-green-50" : "bg-red-50"
            }`}
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
                <span className="text-gray-400">
                  {isPositive ? "+" : "-"}
                </span>
                <button
                  onClick={() => onTickerClick?.(pair.ticker_b)}
                  className="font-semibold text-blue-600 hover:underline"
                >
                  {pair.ticker_b}
                </button>
              </div>

              <div className="flex items-center gap-6">
                <div className="text-right">
                  <div className="text-sm text-gray-500">Correlation</div>
                  <div
                    className={`font-bold ${
                      isPositive ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    {pair.correlation >= 0 ? "+" : ""}
                    {pair.correlation.toFixed(3)}
                  </div>
                </div>

                <div className="text-right min-w-[80px]">
                  <div className="text-sm text-gray-500">Strength</div>
                  <div className="font-medium">{strength}</div>
                </div>

                <div className="text-right min-w-[80px]">
                  <div className="text-sm text-gray-500">Data Points</div>
                  <div className="font-medium">{pair.shared_periods}</div>
                </div>
              </div>
            </div>

            {/* Sentiment averages */}
            <div className="mt-2 pt-2 border-t border-gray-200 flex gap-6 text-sm">
              <div>
                <span className="text-gray-500">{pair.ticker_a} avg:</span>{" "}
                <span
                  className={
                    pair.avg_sentiment_a >= 0 ? "text-green-600" : "text-red-600"
                  }
                >
                  {pair.avg_sentiment_a >= 0 ? "+" : ""}
                  {pair.avg_sentiment_a.toFixed(2)}
                </span>
              </div>
              <div>
                <span className="text-gray-500">{pair.ticker_b} avg:</span>{" "}
                <span
                  className={
                    pair.avg_sentiment_b >= 0 ? "text-green-600" : "text-red-600"
                  }
                >
                  {pair.avg_sentiment_b >= 0 ? "+" : ""}
                  {pair.avg_sentiment_b.toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
