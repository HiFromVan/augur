"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from "recharts";

interface LeagueStats {
  league: string;
  total_predictions: number;
  correct_predictions: number;
  accuracy_percentage: number;
  avg_rps: number;
  exact_score_matches: number;
}

interface LeagueStatsChartProps {
  data: LeagueStats[];
}

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

export function LeagueStatsChart({ data }: LeagueStatsChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-[300px] flex items-center justify-center text-muted-foreground">
        暂无数据
      </div>
    );
  }

  // 按预测数量排序，取前6个
  const chartData = [...data]
    .sort((a, b) => b.total_predictions - a.total_predictions)
    .slice(0, 6);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="league"
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
          formatter={(value) => `${Number(value).toFixed(1)}%`}
        />
        <Legend />
        <Bar dataKey="accuracy_percentage" name="准确率 (%)">
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
