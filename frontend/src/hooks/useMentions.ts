import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getMentions,
  deleteMention,
  deleteMentionsBulk,
  getFilterOptions,
} from "../api/client";
import type { MentionFilters } from "../types";

// Query keys for mentions
export const mentionQueryKeys = {
  mentions: (page: number, pageSize: number, filters: MentionFilters) =>
    ["mentions", page, pageSize, filters] as const,
  filterOptions: ["filterOptions"] as const,
};

// Mentions list hook with pagination and filters
export function useMentions(
  page: number,
  pageSize: number,
  filters: MentionFilters
) {
  return useQuery({
    queryKey: mentionQueryKeys.mentions(page, pageSize, filters),
    queryFn: () => getMentions(page, pageSize, filters),
    staleTime: 30000, // 30 seconds
    placeholderData: (previousData) => previousData, // Keep previous data while loading new page
  });
}

// Filter options hook (distinct tickers and subreddits)
export function useFilterOptions() {
  return useQuery({
    queryKey: mentionQueryKeys.filterOptions,
    queryFn: getFilterOptions,
    staleTime: 60000, // 1 minute - filter options don't change often
  });
}

// Delete single mention mutation
export function useDeleteMention() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteMention,
    onSuccess: () => {
      // Invalidate mentions list and stats
      queryClient.invalidateQueries({ queryKey: ["mentions"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["filterOptions"] });
    },
  });
}

// Bulk delete mentions mutation
export function useDeleteMentionsBulk() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteMentionsBulk,
    onSuccess: () => {
      // Invalidate mentions list and stats
      queryClient.invalidateQueries({ queryKey: ["mentions"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["filterOptions"] });
    },
  });
}
