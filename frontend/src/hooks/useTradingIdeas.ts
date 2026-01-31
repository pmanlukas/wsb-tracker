import { useQuery } from "@tanstack/react-query";
import {
  getTradingIdeas,
  getTradingIdeasSummary,
  getTradingIdeasFilterOptions,
  getTradingIdeasByTicker,
  getTradingIdea,
  getLLMStatus,
  getLLMUsage,
} from "../api/client";
import type { TradingIdeasFilters } from "../types";

// Query keys
export const tradingIdeasKeys = {
  all: ["trading-ideas"] as const,
  list: (page: number, pageSize: number, filters: TradingIdeasFilters) =>
    [...tradingIdeasKeys.all, "list", { page, pageSize, filters }] as const,
  summary: (hours: number) =>
    [...tradingIdeasKeys.all, "summary", hours] as const,
  filterOptions: () => [...tradingIdeasKeys.all, "filter-options"] as const,
  byTicker: (ticker: string, hours: number) =>
    [...tradingIdeasKeys.all, "ticker", ticker, hours] as const,
  detail: (id: number) => [...tradingIdeasKeys.all, "detail", id] as const,
};

export const llmKeys = {
  all: ["llm"] as const,
  status: () => [...llmKeys.all, "status"] as const,
  usage: (days: number) => [...llmKeys.all, "usage", days] as const,
};

// Trading Ideas Hooks
export function useTradingIdeas(
  page: number = 1,
  pageSize: number = 25,
  filters: TradingIdeasFilters = {}
) {
  return useQuery({
    queryKey: tradingIdeasKeys.list(page, pageSize, filters),
    queryFn: () => getTradingIdeas(page, pageSize, filters),
    staleTime: 30 * 1000, // 30 seconds
  });
}

export function useTradingIdeasSummary(hours: number = 24) {
  return useQuery({
    queryKey: tradingIdeasKeys.summary(hours),
    queryFn: () => getTradingIdeasSummary(hours),
    staleTime: 30 * 1000,
  });
}

export function useTradingIdeasFilterOptions() {
  return useQuery({
    queryKey: tradingIdeasKeys.filterOptions(),
    queryFn: getTradingIdeasFilterOptions,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useTradingIdeasByTicker(
  ticker: string,
  hours: number = 24,
  limit: number = 20
) {
  return useQuery({
    queryKey: tradingIdeasKeys.byTicker(ticker, hours),
    queryFn: () => getTradingIdeasByTicker(ticker, hours, limit),
    enabled: !!ticker,
    staleTime: 30 * 1000,
  });
}

export function useTradingIdea(id: number) {
  return useQuery({
    queryKey: tradingIdeasKeys.detail(id),
    queryFn: () => getTradingIdea(id),
    enabled: id > 0,
    staleTime: 60 * 1000,
  });
}

// LLM Hooks
export function useLLMStatus() {
  return useQuery({
    queryKey: llmKeys.status(),
    queryFn: getLLMStatus,
    staleTime: 30 * 1000,
  });
}

export function useLLMUsage(days: number = 30) {
  return useQuery({
    queryKey: llmKeys.usage(days),
    queryFn: () => getLLMUsage(days),
    staleTime: 60 * 1000,
  });
}
