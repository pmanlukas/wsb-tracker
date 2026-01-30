import { useState, useEffect } from "react";
import { Bell, X, Check, AlertTriangle } from "lucide-react";
import { useAlerts, useAcknowledgeAlert, useAcknowledgeAllAlerts } from "../hooks/useTickers";
import type { NewAlertData, Alert } from "../types";

interface AlertBannerProps {
  newAlert: NewAlertData | null;
}

export function AlertBanner({ newAlert }: AlertBannerProps) {
  const [showPanel, setShowPanel] = useState(false);
  const [notification, setNotification] = useState<NewAlertData | null>(null);
  const { data, refetch } = useAlerts(true, 20);
  const ackMutation = useAcknowledgeAlert();
  const ackAllMutation = useAcknowledgeAllAlerts();

  // Show notification for new alerts
  useEffect(() => {
    if (newAlert) {
      setNotification(newAlert);
      refetch();

      // Auto-dismiss after 5 seconds
      const timer = setTimeout(() => {
        setNotification(null);
      }, 5000);

      // Request browser notification permission
      if (Notification.permission === "granted") {
        new Notification(`WSB Alert: ${newAlert.ticker}`, {
          body: newAlert.message,
          icon: "/favicon.ico",
        });
      }

      return () => clearTimeout(timer);
    }
  }, [newAlert, refetch]);

  const handleAcknowledge = async (alertId: number) => {
    await ackMutation.mutateAsync(alertId);
  };

  const handleAcknowledgeAll = async () => {
    await ackAllMutation.mutateAsync();
  };

  const requestNotificationPermission = () => {
    Notification.requestPermission();
  };

  const unacknowledgedCount = data?.unacknowledged ?? 0;

  return (
    <>
      {/* Toast Notification */}
      {notification && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className="bg-wsb-orange/90 text-white p-4 rounded-lg shadow-lg max-w-sm">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="font-bold">{notification.ticker}</div>
                <div className="text-sm opacity-90">{notification.message}</div>
                <div className="text-xs opacity-75 mt-1">
                  Heat Score: {notification.heat_score.toFixed(1)}
                </div>
              </div>
              <button
                onClick={() => setNotification(null)}
                className="hover:bg-white/20 p-1 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Alert Bell */}
      <div className="relative">
        <button
          onClick={() => setShowPanel(!showPanel)}
          className="relative p-2 hover:bg-gray-700 rounded-lg transition-colors"
        >
          <Bell className="w-5 h-5" />
          {unacknowledgedCount > 0 && (
            <span className="absolute -top-1 -right-1 bg-wsb-red text-white text-xs w-5 h-5 rounded-full flex items-center justify-center">
              {unacknowledgedCount > 9 ? "9+" : unacknowledgedCount}
            </span>
          )}
        </button>

        {/* Alert Panel */}
        {showPanel && (
          <div className="absolute right-0 top-full mt-2 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50">
            <div className="p-3 border-b border-gray-700 flex items-center justify-between">
              <span className="font-semibold">Alerts</span>
              <div className="flex gap-2">
                {Notification.permission !== "granted" && (
                  <button
                    onClick={requestNotificationPermission}
                    className="text-xs text-wsb-blue hover:underline"
                  >
                    Enable notifications
                  </button>
                )}
                {unacknowledgedCount > 0 && (
                  <button
                    onClick={handleAcknowledgeAll}
                    className="text-xs text-gray-400 hover:text-white"
                  >
                    Acknowledge all
                  </button>
                )}
              </div>
            </div>
            <div className="max-h-80 overflow-y-auto">
              {data?.alerts && data.alerts.length > 0 ? (
                data.alerts.map((alert: Alert) => (
                  <div
                    key={alert.id}
                    className={`p-3 border-b border-gray-700/50 ${
                      !alert.acknowledged ? "bg-gray-700/30" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-wsb-blue">
                            {alert.ticker}
                          </span>
                          <span className="text-xs px-2 py-0.5 bg-gray-700 rounded">
                            {alert.alert_type}
                          </span>
                        </div>
                        <div className="text-sm text-gray-300 mt-1">
                          {alert.message}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {new Date(alert.triggered_at).toLocaleString()}
                        </div>
                      </div>
                      {!alert.acknowledged && (
                        <button
                          onClick={() => handleAcknowledge(alert.id)}
                          className="p-1 hover:bg-gray-600 rounded"
                          title="Acknowledge"
                        >
                          <Check className="w-4 h-4 text-wsb-green" />
                        </button>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-center text-gray-500 text-sm">
                  No alerts
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
