import { useState, useMemo } from "react";
import {
  Search,
  Filter,
  Trash2,
  ChevronUp,
  ChevronDown,
  X,
  TrendingUp,
  TrendingDown,
  Minus,
  FileText,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { useMentions, useFilterOptions, useDeleteMention, useDeleteMentionsBulk } from "../hooks/useMentions";
import { Pagination } from "./Pagination";
import { ConfirmDialog } from "./ConfirmDialog";
import type { MentionFilters, MentionDetail } from "../types";

type SortField = "timestamp" | "ticker" | "sentiment_compound" | "post_score" | "subreddit";

export function DatabaseExplorer() {
  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  // Filter state
  const [showFilters, setShowFilters] = useState(false);
  const [tickerFilter, setTickerFilter] = useState("");
  const [subredditFilter, setSubredditFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sentimentMin, setSentimentMin] = useState<string>("");
  const [sentimentMax, setSentimentMax] = useState<string>("");

  // Sort state
  const [sortBy, setSortBy] = useState<SortField>("timestamp");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectAll, setSelectAll] = useState(false);

  // Modal state
  const [selectedMention, setSelectedMention] = useState<MentionDetail | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{ type: "single" | "bulk"; ids: number[] } | null>(null);

  // Build filters object
  const filters: MentionFilters = useMemo(
    () => ({
      ticker: tickerFilter || undefined,
      subreddit: subredditFilter || undefined,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
      sentimentMin: sentimentMin ? parseFloat(sentimentMin) : undefined,
      sentimentMax: sentimentMax ? parseFloat(sentimentMax) : undefined,
      sortBy,
      sortOrder,
    }),
    [tickerFilter, subredditFilter, dateFrom, dateTo, sentimentMin, sentimentMax, sortBy, sortOrder]
  );

  // Queries
  const { data, isLoading, error } = useMentions(page, pageSize, filters);
  const { data: filterOptions } = useFilterOptions();

  // Mutations
  const deleteMutation = useDeleteMention();
  const deleteBulkMutation = useDeleteMentionsBulk();

  // Reset page when filters change
  const handleFilterChange = () => {
    setPage(1);
    setSelectedIds(new Set());
    setSelectAll(false);
  };

  // Sort handler
  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
    handleFilterChange();
  };

  // Selection handlers
  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedIds(new Set());
      setSelectAll(false);
    } else if (data?.mentions) {
      setSelectedIds(new Set(data.mentions.map((m) => m.id)));
      setSelectAll(true);
    }
  };

  const handleSelectOne = (id: number) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
    setSelectAll(false);
  };

  // Delete handlers
  const handleDeleteConfirm = () => {
    if (!confirmDelete) return;

    if (confirmDelete.type === "single") {
      deleteMutation.mutate(confirmDelete.ids[0], {
        onSuccess: () => {
          setConfirmDelete(null);
          setSelectedMention(null);
        },
      });
    } else {
      deleteBulkMutation.mutate(confirmDelete.ids, {
        onSuccess: () => {
          setConfirmDelete(null);
          setSelectedIds(new Set());
          setSelectAll(false);
        },
      });
    }
  };

  // Clear filters
  const clearFilters = () => {
    setTickerFilter("");
    setSubredditFilter("");
    setDateFrom("");
    setDateTo("");
    setSentimentMin("");
    setSentimentMax("");
    handleFilterChange();
  };

  const hasActiveFilters = tickerFilter || subredditFilter || dateFrom || dateTo || sentimentMin || sentimentMax;

  // Render helpers
  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortBy !== field) return null;
    return sortOrder === "asc" ? (
      <ChevronUp className="inline w-4 h-4" />
    ) : (
      <ChevronDown className="inline w-4 h-4" />
    );
  };

  const getSentimentIcon = (label: string) => {
    switch (label) {
      case "bullish":
        return <TrendingUp className="w-4 h-4 text-wsb-green" />;
      case "bearish":
        return <TrendingDown className="w-4 h-4 text-wsb-red" />;
      default:
        return <Minus className="w-4 h-4 text-gray-400" />;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header with filters toggle and bulk actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold text-white">Database Explorer</h2>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors ${
              showFilters || hasActiveFilters
                ? "bg-wsb-blue text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
          >
            <Filter className="w-4 h-4" />
            Filters
            {hasActiveFilters && (
              <span className="ml-1 px-1.5 py-0.5 text-xs bg-white/20 rounded">
                Active
              </span>
            )}
          </button>
        </div>

        {selectedIds.size > 0 && (
          <button
            onClick={() => setConfirmDelete({ type: "bulk", ids: Array.from(selectedIds) })}
            className="flex items-center gap-2 px-3 py-1.5 bg-wsb-red text-white rounded text-sm hover:bg-red-600 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Delete {selectedIds.size} selected
          </button>
        )}
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="card p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {/* Ticker filter */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Ticker</label>
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input
                  type="text"
                  value={tickerFilter}
                  onChange={(e) => {
                    setTickerFilter(e.target.value.toUpperCase());
                    handleFilterChange();
                  }}
                  placeholder="e.g. GME"
                  list="ticker-options"
                  className="w-full pl-8 pr-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-wsb-blue"
                />
                <datalist id="ticker-options">
                  {filterOptions?.tickers.map((t) => (
                    <option key={t} value={t} />
                  ))}
                </datalist>
              </div>
            </div>

            {/* Subreddit filter */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Subreddit</label>
              <select
                value={subredditFilter}
                onChange={(e) => {
                  setSubredditFilter(e.target.value);
                  handleFilterChange();
                }}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-wsb-blue"
              >
                <option value="">All subreddits</option>
                {filterOptions?.subreddits.map((s) => (
                  <option key={s} value={s}>
                    r/{s}
                  </option>
                ))}
              </select>
            </div>

            {/* Date from */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">From Date</label>
              <input
                type="datetime-local"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  handleFilterChange();
                }}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-wsb-blue"
              />
            </div>

            {/* Date to */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">To Date</label>
              <input
                type="datetime-local"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  handleFilterChange();
                }}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-wsb-blue"
              />
            </div>

            {/* Sentiment range */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Sentiment Min</label>
              <input
                type="number"
                min="-1"
                max="1"
                step="0.1"
                value={sentimentMin}
                onChange={(e) => {
                  setSentimentMin(e.target.value);
                  handleFilterChange();
                }}
                placeholder="-1.0"
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-wsb-blue"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1">Sentiment Max</label>
              <input
                type="number"
                min="-1"
                max="1"
                step="0.1"
                value={sentimentMax}
                onChange={(e) => {
                  setSentimentMax(e.target.value);
                  handleFilterChange();
                }}
                placeholder="1.0"
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-wsb-blue"
              />
            </div>
          </div>

          {hasActiveFilters && (
            <div className="flex justify-end">
              <button
                onClick={clearFilters}
                className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
                Clear all filters
              </button>
            </div>
          )}
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-wsb-blue" />
          </div>
        ) : error ? (
          <div className="text-center py-12 text-wsb-red">
            Failed to load mentions: {error.message}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700 text-gray-400">
                    <th className="px-4 py-3 text-left w-10">
                      <input
                        type="checkbox"
                        checked={selectAll}
                        onChange={handleSelectAll}
                        className="rounded bg-gray-700 border-gray-600 text-wsb-blue focus:ring-wsb-blue"
                      />
                    </th>
                    <th
                      className="px-4 py-3 text-left cursor-pointer hover:text-white"
                      onClick={() => handleSort("ticker")}
                    >
                      Ticker <SortIcon field="ticker" />
                    </th>
                    <th className="px-4 py-3 text-left">Post Title</th>
                    <th
                      className="px-4 py-3 text-left cursor-pointer hover:text-white"
                      onClick={() => handleSort("subreddit")}
                    >
                      Subreddit <SortIcon field="subreddit" />
                    </th>
                    <th
                      className="px-4 py-3 text-center cursor-pointer hover:text-white"
                      onClick={() => handleSort("sentiment_compound")}
                    >
                      Sentiment <SortIcon field="sentiment_compound" />
                    </th>
                    <th
                      className="px-4 py-3 text-right cursor-pointer hover:text-white"
                      onClick={() => handleSort("post_score")}
                    >
                      Score <SortIcon field="post_score" />
                    </th>
                    <th
                      className="px-4 py-3 text-right cursor-pointer hover:text-white"
                      onClick={() => handleSort("timestamp")}
                    >
                      Date <SortIcon field="timestamp" />
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data?.mentions.map((mention) => (
                    <tr
                      key={mention.id}
                      className="border-b border-gray-700/50 hover:bg-gray-800/50 cursor-pointer transition-colors"
                      onClick={(e) => {
                        // Don't open detail if clicking checkbox
                        if ((e.target as HTMLElement).tagName !== "INPUT") {
                          setSelectedMention(mention);
                        }
                      }}
                    >
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(mention.id)}
                          onChange={() => handleSelectOne(mention.id)}
                          className="rounded bg-gray-700 border-gray-600 text-wsb-blue focus:ring-wsb-blue"
                        />
                      </td>
                      <td className="px-4 py-3 font-mono font-bold text-wsb-blue">
                        {mention.ticker}
                        {mention.is_dd_post && (
                          <span className="ml-1 text-xs text-wsb-orange">DD</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-300 max-w-[300px] truncate">
                        {mention.post_title}
                      </td>
                      <td className="px-4 py-3 text-gray-400">r/{mention.subreddit}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-2">
                          {getSentimentIcon(mention.sentiment_label)}
                          <span
                            className={`text-xs ${
                              mention.sentiment_label === "bullish"
                                ? "text-wsb-green"
                                : mention.sentiment_label === "bearish"
                                ? "text-wsb-red"
                                : "text-gray-400"
                            }`}
                          >
                            {mention.sentiment_compound.toFixed(2)}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right text-gray-300">
                        {mention.post_score.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-400 text-xs">
                        {new Date(mention.timestamp).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {data && data.mentions.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                No mentions found matching your filters.
              </div>
            )}

            {data && data.total > 0 && (
              <Pagination
                page={page}
                totalPages={data.total_pages}
                pageSize={pageSize}
                total={data.total}
                onPageChange={setPage}
                onPageSizeChange={(size) => {
                  setPageSize(size);
                  setPage(1);
                }}
              />
            )}
          </>
        )}
      </div>

      {/* Mention detail modal */}
      {selectedMention && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/70"
            onClick={() => setSelectedMention(null)}
          />
          <div className="relative bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto animate-slide-in">
            <div className="sticky top-0 bg-gray-800 border-b border-gray-700 px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-xl font-mono font-bold text-wsb-blue">
                  ${selectedMention.ticker}
                </span>
                {selectedMention.is_dd_post && (
                  <span className="flex items-center gap-1 px-2 py-0.5 bg-wsb-orange/20 text-wsb-orange rounded text-xs">
                    <FileText className="w-3 h-3" />
                    DD
                  </span>
                )}
              </div>
              <button
                onClick={() => setSelectedMention(null)}
                className="text-gray-500 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Post info */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  {selectedMention.post_title}
                </h3>
                <div className="flex items-center gap-4 text-sm text-gray-400">
                  <span>r/{selectedMention.subreddit}</span>
                  <span>{selectedMention.post_score.toLocaleString()} points</span>
                  <span>{new Date(selectedMention.timestamp).toLocaleString()}</span>
                  <a
                    href={`https://reddit.com/r/${selectedMention.subreddit}/comments/${selectedMention.post_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-wsb-blue hover:underline"
                  >
                    View on Reddit
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>

              {/* Sentiment */}
              <div className="flex items-center gap-4 p-4 bg-gray-700/50 rounded-lg">
                <div className="flex items-center gap-2">
                  {getSentimentIcon(selectedMention.sentiment_label)}
                  <span className="text-lg font-semibold text-white capitalize">
                    {selectedMention.sentiment_label}
                  </span>
                </div>
                <div className="text-sm text-gray-400">
                  Score: {selectedMention.sentiment_compound.toFixed(4)}
                </div>
              </div>

              {/* Context */}
              <div>
                <h4 className="text-sm font-semibold text-gray-400 mb-2">Context</h4>
                <div className="p-4 bg-gray-900 rounded-lg text-gray-300 text-sm whitespace-pre-wrap">
                  {selectedMention.context || "No context available"}
                </div>
              </div>

              {/* Flair */}
              {selectedMention.post_flair && (
                <div className="text-sm">
                  <span className="text-gray-400">Flair: </span>
                  <span className="px-2 py-0.5 bg-gray-700 rounded text-gray-300">
                    {selectedMention.post_flair}
                  </span>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="sticky bottom-0 bg-gray-800 border-t border-gray-700 px-6 py-4 flex justify-end gap-3">
              <button
                onClick={() => setSelectedMention(null)}
                className="px-4 py-2 text-gray-300 hover:text-white hover:bg-gray-700 rounded transition-colors"
              >
                Close
              </button>
              <button
                onClick={() =>
                  setConfirmDelete({ type: "single", ids: [selectedMention.id] })
                }
                className="flex items-center gap-2 px-4 py-2 bg-wsb-red text-white rounded hover:bg-red-600 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm delete dialog */}
      <ConfirmDialog
        isOpen={confirmDelete !== null}
        title={confirmDelete?.type === "bulk" ? "Delete Multiple Mentions" : "Delete Mention"}
        message={
          confirmDelete?.type === "bulk"
            ? `Are you sure you want to delete ${confirmDelete.ids.length} mentions? This action cannot be undone.`
            : "Are you sure you want to delete this mention? This action cannot be undone."
        }
        confirmLabel="Delete"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setConfirmDelete(null)}
        variant="danger"
      />
    </div>
  );
}
