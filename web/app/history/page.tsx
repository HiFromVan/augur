"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { NavBar } from "@/components/NavBar";
import { DataQualityPanel } from "@/components/DataQualityPanel";
import { AccuracyChart } from "@/components/AccuracyChart";
import { LeagueStatsChart } from "@/components/LeagueStatsChart";
import { TrendingUp, Target, Award, BarChart3 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface AccuracyStats {
  total_predictions: number;
  correct_predictions: number;
  accuracy_percentage: number;
  avg_rps: number;
  exact_score_matches: number;
  avg_score_diff: number;
}

interface TrendData {
  date: string;
  total: number;
  correct: number;
  accuracy: number;
  avg_rps: number;
}

interface LeagueStats {
  league: string;
  total_predictions: number;
  correct_predictions: number;
  accuracy_percentage: number;
  avg_rps: number;
  exact_score_matches: number;
}

interface PredictionRecord {
  id: number;
  match_id: number;
  match_date: string;
  league: string;
  league_cn: string;
  home_team: string;
  away_team: string;
  home_team_cn: string;
  away_team_cn: string;
  pred_home: number;
  pred_draw: number;
  pred_away: number;
  pred_score_home: number | null;
  pred_score_away: number | null;
  actual_home: number | null;
  actual_away: number | null;
  is_correct: boolean | null;
  score_exact_match: boolean | null;
  rps_score: number | null;
  odds_home: number | null;
  odds_draw: number | null;
  odds_away: number | null;
  predicted_at: string | null;
  evaluated_at: string | null;
}

export default function HistoryPage() {
  const [stats, setStats] = useState<AccuracyStats | null>(null);
  const [trendData, setTrendData] = useState<TrendData[]>([]);
  const [leagueStats, setLeagueStats] = useState<LeagueStats[]>([]);
  const [predictions, setPredictions] = useState<PredictionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("evaluated");

  useEffect(() => {
    fetchData();
  }, [page, statusFilter]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, trendRes, leagueRes, predictionsRes] = await Promise.all([
        fetch(`${API_BASE}/api/stats/accuracy`),
        fetch(`${API_BASE}/api/stats/accuracy-trend?days=30`),
        fetch(`${API_BASE}/api/stats/accuracy-by-league`),
        fetch(`${API_BASE}/api/stats/predictions?page=${page}&limit=20&status=${statusFilter}`),
      ]);

      const [statsData, trendData, leagueData, predictionsData] = await Promise.all([
        statsRes.json(),
        trendRes.json(),
        leagueRes.json(),
        predictionsRes.json(),
      ]);

      setStats(statsData);
      setTrendData(trendData.trend || []);
      setLeagueStats(leagueData.leagues || []);
      setPredictions(predictionsData.predictions || []);
      setTotalPages(predictionsData.total_pages || 1);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  };

  const getPredictionResult = (pred: PredictionRecord) => {
    const maxProb = Math.max(pred.pred_home, pred.pred_draw, pred.pred_away);
    if (maxProb === pred.pred_home) return "主胜";
    if (maxProb === pred.pred_draw) return "平局";
    return "客胜";
  };

  const getActualResult = (pred: PredictionRecord) => {
    if (pred.actual_home === null || pred.actual_away === null) return "待定";
    if (pred.actual_home > pred.actual_away) return "主胜";
    if (pred.actual_home === pred.actual_away) return "平局";
    return "客胜";
  };

  if (loading && !stats) {
    return (
      <div className="min-h-screen pt-24 px-6">
        <div className="max-w-7xl mx-auto">
          <p className="text-center text-muted-foreground">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <NavBar />
      <div className="min-h-screen pt-24 px-6 pb-12">
        <div className="max-w-7xl mx-auto space-y-8">
        {/* 标题 */}
        <div>
          <h1 className="text-3xl font-bold">历史预测</h1>
          <p className="text-muted-foreground mt-2">
            查看预测准确率、趋势分析和详细记录
          </p>
        </div>

        {/* 顶部统计卡片 */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">总预测数</p>
                    <p className="text-2xl font-bold mt-1">{stats.total_predictions}</p>
                  </div>
                  <BarChart3 className="h-8 w-8 text-blue-500" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">准确率</p>
                    <p className="text-2xl font-bold mt-1">
                      {stats.accuracy_percentage.toFixed(1)}%
                    </p>
                  </div>
                  <Target className="h-8 w-8 text-green-500" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">RPS 评分</p>
                    <p className="text-2xl font-bold mt-1">
                      {stats.avg_rps.toFixed(4)}
                    </p>
                  </div>
                  <TrendingUp className="h-8 w-8 text-orange-500" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">精确比分</p>
                    <p className="text-2xl font-bold mt-1">
                      {stats.exact_score_matches}
                      <span className="text-sm text-muted-foreground ml-1">
                        ({((stats.exact_score_matches / stats.total_predictions) * 100).toFixed(1)}%)
                      </span>
                    </p>
                  </div>
                  <Award className="h-8 w-8 text-purple-500" />
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* 趋势图表 */}
        <Card>
          <CardHeader>
            <CardTitle>📈 数据分析</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="trend" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="trend">准确率趋势</TabsTrigger>
                <TabsTrigger value="league">按联赛统计</TabsTrigger>
              </TabsList>
              <TabsContent value="trend" className="mt-4">
                <AccuracyChart data={trendData} />
              </TabsContent>
              <TabsContent value="league" className="mt-4">
                <LeagueStatsChart data={leagueStats} />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* 数据质量监控 */}
        <DataQualityPanel />

        {/* 预测记录列表 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>🎯 预测记录</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setStatusFilter("evaluated")}
                  className={`px-3 py-1 text-sm rounded-md ${
                    statusFilter === "evaluated"
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground"
                  }`}
                >
                  已结束
                </button>
                <button
                  onClick={() => setStatusFilter("all")}
                  className={`px-3 py-1 text-sm rounded-md ${
                    statusFilter === "all"
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground"
                  }`}
                >
                  全部
                </button>
                <button
                  onClick={() => setStatusFilter("correct")}
                  className={`px-3 py-1 text-sm rounded-md ${
                    statusFilter === "correct"
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground"
                  }`}
                >
                  正确
                </button>
                <button
                  onClick={() => setStatusFilter("incorrect")}
                  className={`px-3 py-1 text-sm rounded-md ${
                    statusFilter === "incorrect"
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground"
                  }`}
                >
                  错误
                </button>
                <button
                  onClick={() => setStatusFilter("pending")}
                  className={`px-3 py-1 text-sm rounded-md ${
                    statusFilter === "pending"
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground"
                  }`}
                >
                  待评估
                </button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {predictions.map((pred) => (
                <div
                  key={pred.id}
                  className="border rounded-lg p-4 hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs text-muted-foreground">
                          {new Date(pred.match_date).toLocaleString("zh-CN")}
                        </span>
                        <Badge variant="outline">{pred.league_cn || pred.league}</Badge>
                      </div>
                      <p className="font-medium mb-2">
                        {pred.home_team_cn || pred.home_team} vs {pred.away_team_cn || pred.away_team}
                      </p>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-muted-foreground mb-1">预测:</p>
                          <p>
                            {getPredictionResult(pred)} (
                            {(Math.max(pred.pred_home, pred.pred_draw, pred.pred_away) * 100).toFixed(1)}%)
                          </p>
                          {pred.pred_score_home !== null && pred.pred_score_away !== null && (
                            <p className="text-muted-foreground">
                              比分: {pred.pred_score_home}-{pred.pred_score_away}
                            </p>
                          )}
                        </div>
                        <div>
                          <p className="text-muted-foreground mb-1">实际:</p>
                          {pred.actual_home !== null && pred.actual_away !== null ? (
                            <>
                              <p>
                                {getActualResult(pred)} ({pred.actual_home}-{pred.actual_away})
                              </p>
                              {pred.score_exact_match && (
                                <Badge variant="default" className="mt-1">
                                  🎯 比分完全正确
                                </Badge>
                              )}
                            </>
                          ) : (
                            <p className="text-muted-foreground">待定</p>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="ml-4">
                      {pred.is_correct === true && (
                        <Badge variant="default" className="bg-green-500">
                          ✓ 正确
                        </Badge>
                      )}
                      {pred.is_correct === false && (
                        <Badge variant="destructive">✗ 错误</Badge>
                      )}
                      {pred.is_correct === null && (
                        <Badge variant="secondary">待评估</Badge>
                      )}
                    </div>
                  </div>
                  {pred.rps_score !== null && (
                    <div className="mt-2 text-xs text-muted-foreground">
                      RPS: {pred.rps_score.toFixed(4)}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* 分页 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-6">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 text-sm border rounded-md disabled:opacity-50"
                >
                  上一页
                </button>
                <span className="text-sm text-muted-foreground">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                  className="px-4 py-2 text-sm border rounded-md disabled:opacity-50"
                >
                  下一页
                </button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
    </>
  );
}
