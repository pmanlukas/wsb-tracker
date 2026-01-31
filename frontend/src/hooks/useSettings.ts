import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getScanSettings,
  updateScanSettings,
  resetScanSettings,
} from "../api/client";
import type { ScanSettingsUpdate } from "../types";

// Query keys for settings
export const settingsQueryKeys = {
  scanSettings: ["scanSettings"] as const,
};

// Scan settings hook
export function useScanSettings() {
  return useQuery({
    queryKey: settingsQueryKeys.scanSettings,
    queryFn: getScanSettings,
    staleTime: Infinity, // Settings don't change unless user updates them
  });
}

// Update scan settings mutation
export function useUpdateScanSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (settings: ScanSettingsUpdate) => updateScanSettings(settings),
    onSuccess: (data) => {
      // Update cache with new settings
      queryClient.setQueryData(settingsQueryKeys.scanSettings, data);
    },
  });
}

// Reset scan settings mutation
export function useResetScanSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: resetScanSettings,
    onSuccess: (data) => {
      // Update cache with reset settings
      queryClient.setQueryData(settingsQueryKeys.scanSettings, data);
    },
  });
}
