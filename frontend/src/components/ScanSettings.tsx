import { useState, useEffect } from "react";
import {
  Save,
  RotateCcw,
  Loader2,
  Check,
  AlertCircle,
  Plus,
  X,
  Info,
} from "lucide-react";
import {
  useScanSettings,
  useUpdateScanSettings,
  useResetScanSettings,
} from "../hooks/useSettings";

export function ScanSettings() {
  // Fetch current settings
  const { data: settings, isLoading, error } = useScanSettings();

  // Mutations
  const updateMutation = useUpdateScanSettings();
  const resetMutation = useResetScanSettings();

  // Local form state
  const [subreddits, setSubreddits] = useState<string[]>([]);
  const [newSubreddit, setNewSubreddit] = useState("");
  const [scanLimit, setScanLimit] = useState(100);
  const [requestDelay, setRequestDelay] = useState(2.0);
  const [minScore, setMinScore] = useState(10);
  const [scanSort, setScanSort] = useState("hot");

  // Success/error message
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Initialize form when settings load
  useEffect(() => {
    if (settings) {
      setSubreddits(settings.subreddits);
      setScanLimit(settings.scan_limit);
      setRequestDelay(settings.request_delay);
      setMinScore(settings.min_score);
      setScanSort(settings.scan_sort);
    }
  }, [settings]);

  // Check if form has changes
  const hasChanges = settings
    ? JSON.stringify({
        subreddits,
        scan_limit: scanLimit,
        request_delay: requestDelay,
        min_score: minScore,
        scan_sort: scanSort,
      }) !==
      JSON.stringify({
        subreddits: settings.subreddits,
        scan_limit: settings.scan_limit,
        request_delay: settings.request_delay,
        min_score: settings.min_score,
        scan_sort: settings.scan_sort,
      })
    : false;

  // Handlers
  const handleAddSubreddit = () => {
    const cleaned = newSubreddit.trim().toLowerCase().replace(/^r\//, "");
    if (cleaned && !subreddits.includes(cleaned)) {
      setSubreddits([...subreddits, cleaned]);
      setNewSubreddit("");
    }
  };

  const handleRemoveSubreddit = (sub: string) => {
    setSubreddits(subreddits.filter((s) => s !== sub));
  };

  const handleSave = () => {
    setMessage(null);
    updateMutation.mutate(
      {
        subreddits,
        scan_limit: scanLimit,
        request_delay: requestDelay,
        min_score: minScore,
        scan_sort: scanSort,
      },
      {
        onSuccess: () => {
          setMessage({ type: "success", text: "Settings saved successfully!" });
          setTimeout(() => setMessage(null), 3000);
        },
        onError: (err) => {
          setMessage({
            type: "error",
            text: err instanceof Error ? err.message : "Failed to save settings",
          });
        },
      }
    );
  };

  const handleReset = () => {
    setMessage(null);
    resetMutation.mutate(undefined, {
      onSuccess: () => {
        setMessage({ type: "success", text: "Settings reset to defaults!" });
        setTimeout(() => setMessage(null), 3000);
      },
      onError: (err) => {
        setMessage({
          type: "error",
          text: err instanceof Error ? err.message : "Failed to reset settings",
        });
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-wsb-blue" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-12 h-12 text-wsb-red mx-auto mb-4" />
        <p className="text-wsb-red">Failed to load settings</p>
        <p className="text-gray-500 text-sm mt-2">
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Scan Settings</h2>
        {message && (
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm animate-slide-in ${
              message.type === "success"
                ? "bg-wsb-green/20 text-wsb-green"
                : "bg-wsb-red/20 text-wsb-red"
            }`}
          >
            {message.type === "success" ? (
              <Check className="w-4 h-4" />
            ) : (
              <AlertCircle className="w-4 h-4" />
            )}
            {message.text}
          </div>
        )}
      </div>

      <div className="card p-6 space-y-6">
        {/* Subreddits */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Subreddits to Monitor
          </label>
          <div className="flex flex-wrap gap-2 mb-3">
            {subreddits.map((sub) => (
              <span
                key={sub}
                className="flex items-center gap-1 px-2 py-1 bg-gray-700 rounded text-sm text-gray-300"
              >
                r/{sub}
                <button
                  onClick={() => handleRemoveSubreddit(sub)}
                  className="text-gray-500 hover:text-wsb-red transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={newSubreddit}
              onChange={(e) => setNewSubreddit(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddSubreddit();
                }
              }}
              placeholder="Add subreddit..."
              className="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-wsb-blue"
            />
            <button
              onClick={handleAddSubreddit}
              className="flex items-center gap-2 px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-500 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Enter subreddit names without the r/ prefix
          </p>
        </div>

        {/* Scan Limit */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Posts per Scan
          </label>
          <input
            type="number"
            min={10}
            max={500}
            value={scanLimit}
            onChange={(e) => setScanLimit(Number(e.target.value))}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-wsb-blue"
          />
          <div className="flex items-start gap-2 mt-2 text-xs text-gray-500">
            <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <p>
              Number of posts to fetch per subreddit per scan. Higher values
              take longer but capture more data. Range: 10-500
            </p>
          </div>
        </div>

        {/* Request Delay */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Request Delay: {requestDelay.toFixed(1)}s
          </label>
          <input
            type="range"
            min={0.5}
            max={10}
            step={0.5}
            value={requestDelay}
            onChange={(e) => setRequestDelay(Number(e.target.value))}
            className="w-full accent-wsb-blue"
          />
          <div className="flex justify-between text-xs text-gray-500">
            <span>0.5s (faster)</span>
            <span>10s (safer)</span>
          </div>
          <div className="flex items-start gap-2 mt-2 text-xs text-gray-500">
            <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <p>
              Delay between API requests to avoid rate limiting. Lower values
              are faster but may get blocked.
            </p>
          </div>
        </div>

        {/* Min Score */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Minimum Post Score
          </label>
          <input
            type="number"
            min={0}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-wsb-blue"
          />
          <div className="flex items-start gap-2 mt-2 text-xs text-gray-500">
            <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <p>
              Only process posts with at least this many upvotes. Higher values
              filter out low-quality content.
            </p>
          </div>
        </div>

        {/* Sort Order */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Sort Order
          </label>
          <select
            value={scanSort}
            onChange={(e) => setScanSort(e.target.value)}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-wsb-blue"
          >
            {settings?.available_sorts.map((sort) => (
              <option key={sort} value={sort}>
                {sort.charAt(0).toUpperCase() + sort.slice(1)}
              </option>
            ))}
          </select>
          <div className="flex items-start gap-2 mt-2 text-xs text-gray-500">
            <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <p>
              How to sort posts when fetching. "Hot" gets trending posts, "New"
              gets recent posts.
            </p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button
          onClick={handleReset}
          disabled={resetMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 text-gray-300 hover:text-white hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
        >
          {resetMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RotateCcw className="w-4 h-4" />
          )}
          Reset to Defaults
        </button>

        <button
          onClick={handleSave}
          disabled={!hasChanges || updateMutation.isPending || subreddits.length === 0}
          className="flex items-center gap-2 px-4 py-2 bg-wsb-green text-white rounded hover:bg-green-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {updateMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save Changes
        </button>
      </div>

      {!hasChanges && (
        <p className="text-center text-sm text-gray-500">
          No unsaved changes
        </p>
      )}
    </div>
  );
}
