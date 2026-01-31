import { useQuery } from "@tanstack/react-query";
import { getPricesBatch, getSparkline, getTickerPrice } from "../api/client";

export const priceQueryKeys = {
  price: (ticker: string) => ["price", ticker] as const,
  prices: (tickers: string[]) => ["prices", tickers.sort().join(",")] as const,
  sparkline: (ticker: string, days: number) => ["sparkline", ticker, days] as const,
};

/**
 * Hook to fetch current price for a single ticker
 */
export function useTickerPrice(ticker: string, enabled: boolean = true) {
  return useQuery({
    queryKey: priceQueryKeys.price(ticker),
    queryFn: () => getTickerPrice(ticker),
    staleTime: 60000, // 1 minute
    refetchInterval: 60000, // Auto-refresh every minute
    enabled: enabled && !!ticker,
  });
}

/**
 * Hook to fetch prices for multiple tickers
 */
export function usePrices(tickers: string[], enabled: boolean = true) {
  return useQuery({
    queryKey: priceQueryKeys.prices(tickers),
    queryFn: () => getPricesBatch(tickers),
    staleTime: 60000, // 1 minute
    refetchInterval: 60000, // Auto-refresh every minute
    enabled: enabled && tickers.length > 0,
  });
}

/**
 * Hook to fetch sparkline data for a ticker
 */
export function useSparkline(ticker: string, days: number = 7, enabled: boolean = true) {
  return useQuery({
    queryKey: priceQueryKeys.sparkline(ticker, days),
    queryFn: () => getSparkline(ticker, days),
    staleTime: 300000, // 5 minutes
    refetchInterval: 300000,
    enabled: enabled && !!ticker,
  });
}
