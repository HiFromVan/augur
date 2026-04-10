"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertCircle, CheckCircle, RefreshCw } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface DataQualityStats {
  last_result_update: string | null;
  missing_results_count: number;
  pending_evaluations: number;
  recent_evaluations: number;
  finished_without_score: number;
  evaluated_without_actual: number;
  missing_results: Array<{
    id: number;
    date: string;
    league: string;
    home_team: string;
    away_team: string;
  }>;
}

export function DataQualityPanel() {
  const [stats, setStats] = useState<DataQualityStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stats/data-quality`);
      const data = await res.json();
      setStats(data);
    } catch (error) {
      console.error("Failed to fetch data quality stats:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">🔍 数据质量监控</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">加载中...</p>
        </CardContent>
      </Card>
    );
  }

  if (!stats) return null;

  const lastUpdate = stats.last_result_update
    ? new Date(stats.last_result_update)
    : null;
  const hoursAgo = lastUpdate
    ? Math.floor((Date.now() - lastUpdate.getTime()) / (1000 * 60 * 60))
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center justify-between">
          <span>🔍 数据质量监控</span>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchStats}
            disabled={loading}
          >
            <RefreshCw className="h-4 w-4 mr-1" />
            刷新
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* 赛果更新状态 */}
        <div className="flex items-start gap-2">
          {hoursAgo !== null && hoursAgo < 24 ? (
            <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
          ) : (
            <AlertCircle className="h-5 w-5 text-yellow-500 mt-0.5" />
          )}
          <div className="flex-1">
            <p className="text-sm font-medium">
              赛果更新
              {hoursAgo !== null && hoursAgo < 24 ? "正常" : "延迟"}
            </p>
            <p className="text-xs text-muted-foreground">
              最后更新: {hoursAgo !== null ? `${hoursAgo} 小时前` : "未知"}
            </p>
          </div>
        </div>

        {/* 缺失赛果 */}
        {stats.missing_results_count > 0 ? (
          <div className="flex items-start gap-2">
            <AlertCircle className="h-5 w-5 text-orange-500 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium">
                {stats.missing_results_count} 场比赛赛果缺失
              </p>
              <p className="text-xs text-muted-foreground">
                超过 24 小时未更新
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2">
            <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium">赛果数据完整</p>
              <p className="text-xs text-muted-foreground">无缺失数据</p>
            </div>
          </div>
        )}

        {/* 预测评估状态 */}
        <div className="flex items-start gap-2">
          {stats.pending_evaluations === 0 ? (
            <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
          ) : (
            <AlertCircle className="h-5 w-5 text-blue-500 mt-0.5" />
          )}
          <div className="flex-1">
            <p className="text-sm font-medium">
              预测评估{stats.pending_evaluations === 0 ? "正常" : "待处理"}
            </p>
            <p className="text-xs text-muted-foreground">
              待评估: {stats.pending_evaluations} 场
            </p>
          </div>
        </div>

        {/* 异常数据提示 */}
        {stats.finished_without_score > 0 && (
          <div className="flex items-start gap-2 pt-2 border-t">
            <AlertCircle className="h-5 w-5 text-red-500 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-600">
                {stats.finished_without_score} 场已完成比赛缺少比分
              </p>
              <p className="text-xs text-muted-foreground">需要手动检查</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
