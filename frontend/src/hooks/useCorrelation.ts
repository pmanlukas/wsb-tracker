import { useQuery } from "@tanstack/react-query";
import {
  getCorrelations,
  getCooccurrences,
  getCorrelationMatrix,
} from "../api/client";
import type { CorrelationFilters } from "../types";

// Query keys for correlation data
export const correlationQueryKeys = {
  all: ["correlation"] as const,
  correlations: (filters: Partial<CorrelationFilters>) =>
    ["correlation", "pairs", filters] as const,
  cooccurrences: (filters: Partial<CorrelationFilters>) =>
    ["correlation", "cooccurrences", filters] as const,
  matrix: (hours: number, limit: number) =>
    ["correlation", "matrix", hours, limit] as const,
};

/**
 * Hook to fetch sentiment correlations between ticker pairs
 */
export function useCorrelations(filters: Partial<CorrelationFilters> = {}) {
  const normalizedFilters: CorrelationFilters = {
    hours: filters.hours ?? 24,
    minMentions: filters.minMentions ?? 5,
    minSharedPeriods: filters.minSharedPeriods ?? 3,
    limit: filters.limit ?? 50,
    ticker: filters.ticker,
  };

  return useQuery({
    queryKey: correlationQueryKeys.correlations(normalizedFilters),
    queryFn: () => getCorrelations(normalizedFilters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to fetch ticker co-occurrence data
 */
export function useCooccurrences(filters: Partial<CorrelationFilters> = {}) {
  const normalizedFilters: CorrelationFilters = {
    hours: filters.hours ?? 24,
    minCooccurrences: filters.minCooccurrences ?? 2,
    limit: filters.limit ?? 50,
    ticker: filters.ticker,
  };

  return useQuery({
    queryKey: correlationQueryKeys.cooccurrences(normalizedFilters),
    queryFn: () => getCooccurrences(normalizedFilters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to fetch correlation matrix for heatmap visualization
 */
export function useCorrelationMatrix(hours: number = 24, limit: number = 15) {
  return useQuery({
    queryKey: correlationQueryKeys.matrix(hours, limit),
    queryFn: () => getCorrelationMatrix(hours, limit),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
