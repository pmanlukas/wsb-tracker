import { useMemo, useState } from "react";
import type { CorrelationMatrixResponse } from "../types";

interface CorrelationHeatmapProps {
  data: CorrelationMatrixResponse;
  onCellClick?: (tickerA: string, tickerB: string, correlation: number) => void;
}

/**
 * Get color for correlation value
 * Red = negative correlation, White = 0, Green = positive correlation
 */
function getCorrelationColor(value: number): string {
  // Clamp value between -1 and 1
  const clamped = Math.max(-1, Math.min(1, value));

  if (clamped === 0) {
    return "rgb(255, 255, 255)";
  }

  if (clamped > 0) {
    // Positive: white to green
    const intensity = Math.round(clamped * 200);
    return `rgb(${255 - intensity}, 255, ${255 - intensity})`;
  } else {
    // Negative: white to red
    const intensity = Math.round(Math.abs(clamped) * 200);
    return `rgb(255, ${255 - intensity}, ${255 - intensity})`;
  }
}

/**
 * Get text color based on background intensity
 */
function getTextColor(value: number): string {
  const absValue = Math.abs(value);
  return absValue > 0.6 ? "white" : "black";
}

export function CorrelationHeatmap({
  data,
  onCellClick,
}: CorrelationHeatmapProps) {
  const [hoveredCell, setHoveredCell] = useState<{
    row: number;
    col: number;
  } | null>(null);

  const { tickers, matrix } = data;

  // Calculate cell size based on number of tickers
  const cellSize = useMemo(() => {
    if (tickers.length <= 10) return 50;
    if (tickers.length <= 15) return 40;
    return 32;
  }, [tickers.length]);

  if (tickers.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        No correlation data available
      </div>
    );
  }

  return (
    <div className="overflow-auto">
      {/* Legend */}
      <div className="flex items-center justify-end gap-4 mb-4 text-sm">
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-4 rounded border"
            style={{ backgroundColor: getCorrelationColor(-1) }}
          />
          <span>-1 (Inverse)</span>
        </div>
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-4 rounded border"
            style={{ backgroundColor: getCorrelationColor(0) }}
          />
          <span>0 (None)</span>
        </div>
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-4 rounded border"
            style={{ backgroundColor: getCorrelationColor(1) }}
          />
          <span>+1 (Direct)</span>
        </div>
      </div>

      {/* Heatmap Grid */}
      <div className="inline-block">
        {/* Header row with ticker labels */}
        <div className="flex">
          <div
            style={{ width: 60, height: cellSize }}
            className="flex-shrink-0"
          />
          {tickers.map((ticker, idx) => (
            <div
              key={`header-${ticker}`}
              style={{ width: cellSize, height: cellSize }}
              className={`flex items-center justify-center text-xs font-medium ${
                hoveredCell?.col === idx ? "bg-blue-100" : ""
              }`}
            >
              <span
                className="transform -rotate-45 whitespace-nowrap overflow-hidden text-ellipsis"
                style={{ maxWidth: cellSize * 1.4 }}
              >
                {ticker}
              </span>
            </div>
          ))}
        </div>

        {/* Data rows */}
        {matrix.map((row, rowIdx) => (
          <div key={`row-${tickers[rowIdx]}`} className="flex">
            {/* Row label */}
            <div
              style={{ width: 60, height: cellSize }}
              className={`flex items-center justify-end pr-2 text-xs font-medium ${
                hoveredCell?.row === rowIdx ? "bg-blue-100" : ""
              }`}
            >
              {tickers[rowIdx]}
            </div>

            {/* Cells */}
            {row.map((value, colIdx) => {
              const isHovered =
                hoveredCell?.row === rowIdx && hoveredCell?.col === colIdx;
              const isDiagonal = rowIdx === colIdx;

              return (
                <div
                  key={`cell-${rowIdx}-${colIdx}`}
                  className={`
                    flex items-center justify-center text-xs font-medium
                    border border-gray-200 transition-all cursor-pointer
                    ${isHovered ? "ring-2 ring-blue-500 z-10" : ""}
                    ${isDiagonal ? "opacity-50" : "hover:ring-2 hover:ring-blue-300"}
                  `}
                  style={{
                    width: cellSize,
                    height: cellSize,
                    backgroundColor: getCorrelationColor(value),
                    color: getTextColor(value),
                  }}
                  onMouseEnter={() =>
                    !isDiagonal && setHoveredCell({ row: rowIdx, col: colIdx })
                  }
                  onMouseLeave={() => setHoveredCell(null)}
                  onClick={() =>
                    !isDiagonal &&
                    onCellClick?.(tickers[rowIdx], tickers[colIdx], value)
                  }
                  title={
                    isDiagonal
                      ? `${tickers[rowIdx]} (self)`
                      : `${tickers[rowIdx]} vs ${tickers[colIdx]}: ${value.toFixed(2)}`
                  }
                >
                  {value.toFixed(2)}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Hover info */}
      {hoveredCell && (
        <div className="mt-4 p-3 bg-gray-100 rounded-lg text-sm">
          <span className="font-medium">
            {tickers[hoveredCell.row]} vs {tickers[hoveredCell.col]}
          </span>
          <span className="mx-2">|</span>
          <span>
            Correlation:{" "}
            <span
              className={`font-bold ${
                matrix[hoveredCell.row][hoveredCell.col] > 0
                  ? "text-green-600"
                  : matrix[hoveredCell.row][hoveredCell.col] < 0
                    ? "text-red-600"
                    : ""
              }`}
            >
              {matrix[hoveredCell.row][hoveredCell.col].toFixed(3)}
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
