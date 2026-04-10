"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

interface TrendData {
  date: string;
  total: number;
  correct: number;
  accuracy: number;
  avg_rps: number;
}

interface AccuracyChartProps {
  data: TrendData[];
}

export function AccuracyChart({ data }: AccuracyChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-[300px] flex items-center justify-center text-muted-foreground">
        暂无数据
      </div>
    );
  }

  // 反转数据顺序，让最新的在右边
  const chartData = [...data].reverse().map((d) => ({
    ...d,
    date: new Date(d.date).toLocaleDateString("zh-CN", {
      month: "numeric",
      day: "numeric",
    }),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="date"
          stroke="#6b7280"
          fontSize={12}
        />
        <YAxis
          stroke="#6b7280"
          fontSize={12}
          domain={[0, 100]}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "8px",
          }}
          formatter={(value, name) => {
            const v = Number(value);
            if (name === "accuracy") return [`${v.toFixed(1)}%`, "准确率"];
            if (name === "avg_rps") return [v.toFixed(4), "RPS"];
            return [value, name];
          }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="accuracy"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={{ r: 4 }}
          name="准确率 (%)"
        />
        <Line
          type="monotone"
          dataKey="avg_rps"
          stroke="#10b981"
          strokeWidth={2}
          dot={{ r: 4 }}
          name="RPS"
          yAxisId={0}
          hide
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
