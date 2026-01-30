import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getTickers,
  getTickerDetail,
  getSnapshots,
  startScan,
  getAlerts,
  acknowledgeAlert,
  acknowledgeAllAlerts,
  getStats,
} from "../api/client";

// Query keys
export const queryKeys = {
  tickers: (hours: number, limit: number) => ["tickers", hours, limit] as const,
  tickerDetail: (symbol: string, hours: number) => ["ticker", symbol, hours] as const,
  snapshots: (limit: number) => ["snapshots", limit] as const,
  alerts: (unacknowledgedOnly: boolean, limit: number) =>
    ["alerts", unacknowledgedOnly, limit] as const,
  stats: ["stats"] as const,
};

// Tickers hook
export function useTickers(hours: number = 24, limit: number = 25) {
  return useQuery({
    queryKey: queryKeys.tickers(hours, limit),
    queryFn: () => getTickers(hours, limit),
    refetchInterval: 60000, // Refetch every minute
    staleTime: 30000, // Consider data stale after 30 seconds
  });
}

// Ticker detail hook
export function useTickerDetail(symbol: string, hours: number = 24) {
  return useQuery({
    queryKey: queryKeys.tickerDetail(symbol, hours),
    queryFn: () => getTickerDetail(symbol, hours),
    enabled: !!symbol,
    staleTime: 30000,
  });
}

// Snapshots hook
export function useSnapshots(limit: number = 10) {
  return useQuery({
    queryKey: queryKeys.snapshots(limit),
    queryFn: () => getSnapshots(limit),
    staleTime: 60000,
  });
}

// Alerts hook
export function useAlerts(unacknowledgedOnly: boolean = false, limit: number = 50) {
  return useQuery({
    queryKey: queryKeys.alerts(unacknowledgedOnly, limit),
    queryFn: () => getAlerts(unacknowledgedOnly, limit),
    refetchInterval: 30000, // Check for new alerts every 30 seconds
    staleTime: 15000,
  });
}

// Stats hook
export function useStats() {
  return useQuery({
    queryKey: queryKeys.stats,
    queryFn: getStats,
    staleTime: 60000,
  });
}

// Scan mutation
export function useScanMutation() {
  return useMutation({
    mutationFn: (limit?: number) => startScan(limit),
  });
}

// Acknowledge alert mutation
export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (alertId: number) => acknowledgeAlert(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

// Acknowledge all alerts mutation
export function useAcknowledgeAllAlerts() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: acknowledgeAllAlerts,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

// Hook to invalidate tickers after scan
export function useInvalidateTickers() {
  const queryClient = useQueryClient();

  return () => {
    queryClient.invalidateQueries({ queryKey: ["tickers"] });
    queryClient.invalidateQueries({ queryKey: ["snapshots"] });
    queryClient.invalidateQueries({ queryKey: ["stats"] });
  };
}
