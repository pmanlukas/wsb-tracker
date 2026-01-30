import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from "recharts";
import type { Mention } from "../types";

interface TickerChartProps {
  mentions: Mention[];
  ticker: string;
}

interface ChartData {
  time: string;
  sentiment: number;
  mentions: number;
  dd: number;
}

export function TickerChart({ mentions, ticker }: TickerChartProps) {
  // Group mentions by hour
  const groupedData = mentions.reduce<Record<string, ChartData>>((acc, mention) => {
    const date = new Date(mention.timestamp);
    const hourKey = `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`;

    if (!acc[hourKey]) {
      acc[hourKey] = {
        time: hourKey,
        sentiment: 0,
        mentions: 0,
        dd: 0,
      };
    }

    acc[hourKey].sentiment += mention.sentiment;
    acc[hourKey].mentions += 1;
    if (mention.is_dd) acc[hourKey].dd += 1;

    return acc;
  }, {});

  // Calculate average sentiment per hour and convert to array
  const chartData = Object.values(groupedData)
    .map((data) => ({
      ...data,
      sentiment: data.mentions > 0 ? data.sentiment / data.mentions : 0,
    }))
    .sort((a, b) => {
      // Sort by time
      const [aDate, aTime] = a.time.split(" ");
      const [bDate, bTime] = b.time.split(" ");
      if (aDate !== bDate) return aDate.localeCompare(bDate);
      return parseInt(aTime) - parseInt(bTime);
    });

  if (chartData.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No data available for chart
      </div>
    );
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-800 border border-gray-700 p-3 rounded-lg shadow-lg">
          <p className="text-gray-400 text-sm">{label}</p>
          {payload.map((entry: any, index: number) => (
            <p
              key={index}
              style={{ color: entry.color }}
              className="text-sm font-medium"
            >
              {entry.name}: {entry.value.toFixed(2)}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Sentiment Trend */}
      <div>
        <h4 className="text-sm font-medium text-gray-400 mb-3">
          Sentiment Trend - {ticker}
        </h4>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="time"
                stroke="#9CA3AF"
                tick={{ fontSize: 10 }}
                interval="preserveStartEnd"
              />
              <YAxis
                stroke="#9CA3AF"
                tick={{ fontSize: 10 }}
                domain={[-1, 1]}
                tickFormatter={(v) => v.toFixed(1)}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="sentiment"
                stroke="#10B981"
                strokeWidth={2}
                dot={false}
                name="Sentiment"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Mention Count */}
      <div>
        <h4 className="text-sm font-medium text-gray-400 mb-3">
          Mentions per Hour
        </h4>
        <div className="h-36">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="time"
                stroke="#9CA3AF"
                tick={{ fontSize: 10 }}
                interval="preserveStartEnd"
              />
              <YAxis stroke="#9CA3AF" tick={{ fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar
                dataKey="mentions"
                fill="#3B82F6"
                name="Mentions"
                radius={[2, 2, 0, 0]}
              />
              <Bar
                dataKey="dd"
                fill="#F59E0B"
                name="DD Posts"
                radius={[2, 2, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
