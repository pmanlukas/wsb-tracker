import { useState, useCallback } from "react";
import { RefreshCw, LayoutDashboard, Database, Settings, Lightbulb, GitCompare } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTickers, useInvalidateTickers } from "../hooks/useTickers";
import { useWebSocket } from "../hooks/useWebSocket";
import { TickerTable } from "./TickerTable";
import { TickerDetail } from "./TickerDetail";
import { ScanStatus } from "./ScanStatus";
import { StatsCard } from "./StatsCard";
import { AlertBanner } from "./AlertBanner";
import { DatabaseExplorer } from "./DatabaseExplorer";
import { ScanSettings } from "./ScanSettings";
import { TradingIdeas } from "./TradingIdeas";
import { CorrelationAnalysis } from "./CorrelationAnalysis";
import type { Ticker, ScanProgressData, ScanCompleteData, NewAlertData } from "../types";

type TabId = "dashboard" | "ideas" | "correlations" | "explorer" | "settings";

export function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");
  const [hours, setHours] = useState(24);
  const [scanProgress, setScanProgress] = useState<ScanProgressData | null>(null);
  const [lastScanResult, setLastScanResult] = useState<ScanCompleteData | null>(null);
  const [newAlert, setNewAlert] = useState<NewAlertData | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<Ticker | null>(null);

  const { data, isLoading, error } = useTickers(hours, 25);
  const invalidateTickers = useInvalidateTickers();
  const queryClient = useQueryClient();

  const handleScanProgress = useCallback((data: ScanProgressData) => {
    setScanProgress(data);
  }, []);

  const handleScanComplete = useCallback(
    (data: ScanCompleteData) => {
      setScanProgress(null);
      setLastScanResult(data);
      invalidateTickers();
    },
    [invalidateTickers]
  );

  const handleNewAlert = useCallback((data: NewAlertData) => {
    setNewAlert(data);
  }, []);

  const { isConnected } = useWebSocket({
    onScanProgress: handleScanProgress,
    onScanComplete: handleScanComplete,
    onNewAlert: handleNewAlert,
  });

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["tickers"] });
  };

  const handleTickerClick = (ticker: Ticker) => {
    setSelectedTicker(ticker);
  };

  const tabs = [
    { id: "dashboard" as const, label: "Dashboard", icon: LayoutDashboard },
    { id: "ideas" as const, label: "Trading Ideas", icon: Lightbulb },
    { id: "correlations" as const, label: "Correlations", icon: GitCompare },
    { id: "explorer" as const, label: "Database Explorer", icon: Database },
    { id: "settings" as const, label: "Settings", icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h1 className="text-2xl font-bold">
                <span className="text-wsb-blue">WSB</span> Tracker
              </h1>
              <span className="text-xs text-gray-500">
                Multi-subreddit stock sentiment tracker
              </span>
            </div>
            <div className="flex items-center gap-4">
              <AlertBanner newAlert={newAlert} />
            </div>
          </div>

          {/* Tab navigation */}
          <nav className="flex gap-1 mt-4 -mb-px">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-t-lg border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "bg-gray-900 text-white border-wsb-blue"
                    : "text-gray-400 border-transparent hover:text-white hover:bg-gray-700/50"
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Dashboard Tab */}
        {activeTab === "dashboard" && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar */}
            <div className="lg:col-span-1 space-y-6">
              <ScanStatus
                isConnected={isConnected}
                scanProgress={scanProgress}
                lastScanResult={lastScanResult}
              />
              <StatsCard />
            </div>

            {/* Main Content */}
            <div className="lg:col-span-3">
              <div className="card">
                {/* Table Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <h2 className="text-xl font-semibold">Top Tickers</h2>
                    <select
                      value={hours}
                      onChange={(e) => setHours(Number(e.target.value))}
                      className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-1 text-sm"
                    >
                      <option value={1}>Last 1 hour</option>
                      <option value={6}>Last 6 hours</option>
                      <option value={12}>Last 12 hours</option>
                      <option value={24}>Last 24 hours</option>
                      <option value={48}>Last 48 hours</option>
                      <option value={168}>Last 7 days</option>
                      <option value={336}>Last 14 days</option>
                      <option value={720}>Last 30 days</option>
                    </select>
                  </div>
                  <button
                    onClick={handleRefresh}
                    className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
                    title="Refresh"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                </div>

                {/* Loading State */}
                {isLoading && (
                  <div className="animate-pulse space-y-3">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div key={i} className="h-12 bg-gray-700 rounded"></div>
                    ))}
                  </div>
                )}

                {/* Error State */}
                {error && (
                  <div className="text-center py-8">
                    <p className="text-wsb-red mb-2">Failed to load tickers</p>
                    <p className="text-gray-500 text-sm">
                      {error instanceof Error ? error.message : "Unknown error"}
                    </p>
                    <button onClick={handleRefresh} className="btn btn-primary mt-4">
                      Retry
                    </button>
                  </div>
                )}

                {/* Table */}
                {data && !isLoading && (
                  <>
                    <TickerTable
                      tickers={data.tickers}
                      onTickerClick={handleTickerClick}
                    />
                    <div className="mt-4 text-xs text-gray-500 text-right">
                      Updated: {new Date(data.updated_at).toLocaleString()}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Trading Ideas Tab */}
        {activeTab === "ideas" && <TradingIdeas />}

        {/* Correlations Tab */}
        {activeTab === "correlations" && (
          <div className="card">
            <CorrelationAnalysis
              onTickerSelect={(ticker) => {
                // Could navigate to dashboard and filter by ticker
                console.log("Selected ticker:", ticker);
              }}
            />
          </div>
        )}

        {/* Database Explorer Tab */}
        {activeTab === "explorer" && <DatabaseExplorer />}

        {/* Settings Tab */}
        {activeTab === "settings" && <ScanSettings />}
      </main>

      {/* Ticker Detail Modal */}
      {selectedTicker && (
        <TickerDetail
          ticker={selectedTicker}
          hours={hours}
          onClose={() => setSelectedTicker(null)}
        />
      )}
    </div>
  );
}
