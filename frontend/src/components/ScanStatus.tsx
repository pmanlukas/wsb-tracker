import { useState } from "react";
import { Play, Loader2, Check, AlertCircle, Wifi, WifiOff } from "lucide-react";
import { useScanMutation } from "../hooks/useTickers";
import type { ScanProgressData, ScanCompleteData } from "../types";

interface ScanStatusProps {
  isConnected: boolean;
  scanProgress: ScanProgressData | null;
  lastScanResult: ScanCompleteData | null;
}

export function ScanStatus({
  isConnected,
  scanProgress,
  lastScanResult,
}: ScanStatusProps) {
  const [scanError, setScanError] = useState<string | null>(null);
  const scanMutation = useScanMutation();

  const handleScan = async () => {
    setScanError(null);
    try {
      await scanMutation.mutateAsync(100);
    } catch (error) {
      setScanError(error instanceof Error ? error.message : "Scan failed");
    }
  };

  const isScanning = scanMutation.isPending || (scanProgress !== null);

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Scan Status</h3>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Wifi className="w-4 h-4 text-wsb-green" />
          ) : (
            <WifiOff className="w-4 h-4 text-wsb-red" />
          )}
          <span className={`text-xs ${isConnected ? "text-wsb-green" : "text-wsb-red"}`}>
            {isConnected ? "Live" : "Disconnected"}
          </span>
        </div>
      </div>

      {/* Scan Progress */}
      {isScanning && scanProgress && (
        <div className="mb-4 p-3 bg-gray-700/50 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Loader2 className="w-4 h-4 animate-spin text-wsb-blue" />
            <span className="text-sm">Scanning...</span>
          </div>
          <div className="text-xs text-gray-400">
            Posts: {scanProgress.posts} | Tickers: {scanProgress.tickers}
          </div>
        </div>
      )}

      {/* Last Scan Result */}
      {!isScanning && lastScanResult && (
        <div className="mb-4 p-3 bg-gray-700/50 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Check className="w-4 h-4 text-wsb-green" />
            <span className="text-sm">Last scan complete</span>
          </div>
          <div className="text-xs text-gray-400">
            {lastScanResult.posts} posts | {lastScanResult.tickers} tickers |{" "}
            {lastScanResult.duration.toFixed(1)}s
          </div>
        </div>
      )}

      {/* Error */}
      {scanError && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-wsb-red" />
            <span className="text-sm text-wsb-red">{scanError}</span>
          </div>
        </div>
      )}

      {/* Scan Button */}
      <button
        onClick={handleScan}
        disabled={isScanning}
        className={`w-full btn ${
          isScanning ? "bg-gray-700 cursor-not-allowed" : "btn-primary"
        } flex items-center justify-center gap-2`}
      >
        {isScanning ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Scanning...
          </>
        ) : (
          <>
            <Play className="w-4 h-4" />
            Start Scan
          </>
        )}
      </button>
    </div>
  );
}
