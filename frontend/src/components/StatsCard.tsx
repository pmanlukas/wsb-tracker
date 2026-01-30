import { Database, MessageSquare, Hash, FileText } from "lucide-react";
import { useStats } from "../hooks/useTickers";

export function StatsCard() {
  const { data, isLoading, error } = useStats();

  if (isLoading) {
    return (
      <div className="card animate-pulse">
        <div className="h-6 bg-gray-700 rounded w-24 mb-4"></div>
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 bg-gray-700 rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">Database Stats</h3>
        <p className="text-gray-500 text-sm">Failed to load stats</p>
      </div>
    );
  }

  // data is returned directly, not nested in a "stats" object
  const statItems = [
    {
      label: "Total Mentions",
      value: data.total_mentions.toLocaleString(),
      icon: MessageSquare,
      color: "text-wsb-blue",
    },
    {
      label: "Unique Tickers",
      value: data.unique_tickers.toLocaleString(),
      icon: Hash,
      color: "text-wsb-green",
    },
    {
      label: "Posts Scanned",
      value: data.total_posts.toLocaleString(),
      icon: FileText,
      color: "text-wsb-orange",
    },
    {
      label: "Database Size",
      value: `${data.database_size_mb.toFixed(1)} MB`,
      icon: Database,
      color: "text-gray-400",
    },
  ];

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">Database Stats</h3>
      <div className="grid grid-cols-2 gap-4">
        {statItems.map((item) => (
          <div key={item.label} className="p-3 bg-gray-700/50 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <item.icon className={`w-4 h-4 ${item.color}`} />
              <span className="text-xs text-gray-400">{item.label}</span>
            </div>
            <div className="text-xl font-bold">{item.value}</div>
          </div>
        ))}
      </div>
      {data.newest_mention && (
        <div className="mt-4 text-xs text-gray-500">
          Latest data: {new Date(data.newest_mention).toLocaleString()}
        </div>
      )}
    </div>
  );
}
