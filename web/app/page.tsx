"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { NavBar } from "@/components/NavBar";
import { MatchCard } from "@/components/MatchCard";
import { useAuth } from "@/contexts/AuthContext";
import { ChatWindow } from "@/components/ChatWindow";

function formatDateLabel(dateStr: string) {
  const d = new Date(dateStr + "T12:00:00");
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diff = (target.getTime() - today.getTime()) / 86400000;
  if (diff === 0) return "今天";
  if (diff === 1) return "明天";
  if (diff === -1) return "昨天";
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return `${d.getMonth() + 1}月${d.getDate()}日 ${weekdays[d.getDay()]}`;
}

function groupByDate(matches: any[]) {
  const groups: Record<string, any[]> = {};
  for (const m of matches) {
    const key = m.date.slice(0, 10);
    if (!groups[key]) groups[key] = [];
    groups[key].push(m);
  }
  for (const key of Object.keys(groups)) {
    groups[key].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  }
  return groups;
}

interface AccuracyStats {
  total_predictions: number;
  correct_predictions: number;
  accuracy_percentage: number;
  avg_rps: number;
  exact_score_matches: number;
  avg_score_diff: number;
}

export default function Home() {
  const { user } = useAuth();
  const [matches, setMatches] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<"6h" | "12h" | "24h" | "all">("all");
  const [accuracyStats, setAccuracyStats] = useState<AccuracyStats | null>(null);

  useEffect(() => {
    const API_BASE = typeof window !== 'undefined' && window.location.hostname.includes('trycloudflare.com')
      ? "https://fee-lease-equal-fisheries.trycloudflare.com"
      : "http://localhost:8000";

    // Convert timeRange to hours parameter
    const hoursParam = timeRange === "all" ? "" :
      timeRange === "6h" ? "?hours=6" :
      timeRange === "12h" ? "?hours=12" : "?hours=24";

    fetch(`${API_BASE}/api/matches${hoursParam}`)
      .then((r) => r.json())
      .then((data) => { setMatches(data.matches || []); setLoading(false); })
      .catch(() => setLoading(false));

    // 获取准确率统计
    fetch(`${API_BASE}/api/stats/accuracy`)
      .then((r) => r.json())
      .then((data) => setAccuracyStats(data))
      .catch(() => {});
  }, [timeRange]);

  // Separate matches by status (backend already filtered by time range)
  const upcoming = matches.filter((m) => m.status === 'pending')
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const live = matches.filter((m) => m.status === 'live')
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const finished = matches.filter((m) => m.status === 'finished')
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  const sorted = [...live, ...upcoming];
  const grouped = groupByDate(sorted);
  const dateKeys = Object.keys(grouped).sort();
  const todayKey = new Date().toISOString().slice(0, 10);

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      {/* Background */}
      <div className="stadium-bg" style={{
        backgroundImage: "url('/stadium.jpg')",
      }}>
        <div className="absolute inset-0 bg-gradient-to-tr from-background via-background/40 to-transparent"></div>
      </div>

      <NavBar />

      {/* Side Navigation - Only show when logged in */}
      {user && (
        <nav className="fixed left-0 top-0 h-full w-20 md:w-64 z-40 backdrop-blur-2xl flex flex-col pt-24 pb-8" style={{ background: "rgba(248, 250, 252, 0.6)" }}>
          <div className="px-6 mb-8 hidden md:block">
            <h2 className="font-[family-name:var(--font-heading)] font-semibold text-lg text-foreground">预测</h2>
            <p className="text-xs text-muted-foreground font-medium">AI 洞察</p>
          </div>
          <div className="flex-1 space-y-2 px-3 md:px-4">
            <button
              onClick={() => setTimeRange("6h")}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all w-full ${
                timeRange === "6h"
                  ? "text-primary font-bold border-r-2 border-primary bg-primary/5 translate-x-1"
                  : "text-muted-foreground hover:text-primary"
              }`}
            >
              <span className="hidden md:block">6小时内</span>
              <span className="md:hidden">6H</span>
              </button>
            <button
              onClick={() => setTimeRange("12h")}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all w-full ${
                timeRange === "12h"
                  ? "text-primary font-bold border-r-2 border-primary bg-primary/5 translate-x-1"
                  : "text-muted-foreground hover:text-primary"
              }`}
            >
              <span className="hidden md:block">12小时内</span>
              <span className="md:hidden">12H</span>
            </button>
            <button
              onClick={() => setTimeRange("24h")}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all w-full ${
                timeRange === "24h"
                  ? "text-primary font-bold border-r-2 border-primary bg-primary/5 translate-x-1"
                  : "text-muted-foreground hover:text-primary"
              }`}
            >
              <span className="hidden md:block">24小时内</span>
              <span className="md:hidden">24H</span>
            </button>
            <button
              onClick={() => setTimeRange("all")}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all w-full ${
                timeRange === "all"
                  ? "text-primary font-bold border-r-2 border-primary bg-primary/5 translate-x-1"
                  : "text-muted-foreground hover:text-primary"
              }`}
            >
              <span className="hidden md:block">所有即将开赛</span>
              <span className="md:hidden">全部</span>
            </button>

          </div>
        </nav>
      )}

      {/* Main Content */}
      <main className={`pt-24 min-h-screen ${user ? 'pl-20 md:pl-64' : ''}`}>
        <div className="max-w-7xl mx-auto px-6 lg:px-12 py-8">
          {loading ? (
            <div className="text-center py-32">
              <p className="text-muted-foreground text-sm">加载中...</p>
            </div>
          ) : (
            <>
              {/* 准确率横幅 - 仅在有数据时显示 */}
              {accuracyStats && accuracyStats.total_predictions > 0 && (
                <div className="mb-8 bg-gradient-to-r from-green-50 to-blue-50 border border-green-200/50 rounded-2xl p-6 backdrop-blur-md">
                  <div className="flex items-center justify-between flex-wrap gap-4">
                    <div>
                      <h3 className="text-lg font-bold text-foreground mb-1 font-[family-name:var(--font-heading)]">
                        预测准确率
                      </h3>
                      <p className="text-sm text-muted-foreground">基于历史预测结果的统计</p>
                    </div>
                    <div className="flex items-center gap-6">
                      <div className="text-center">
                        <div className="text-3xl font-bold text-green-600">
                          {accuracyStats.accuracy_percentage.toFixed(1)}%
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">胜平负准确率</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-blue-600">
                          {accuracyStats.avg_rps.toFixed(4)}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">RPS 评分</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-purple-600">
                          {accuracyStats.total_predictions}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">已评估场次</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* 未登录 - 只显示1场每日推荐 */}
              {!user ? (
                <>
                  <div className="mb-8">
                    <h2 className="text-3xl font-bold text-foreground mb-2 font-[family-name:var(--font-heading)]">每日推荐</h2>
                    <p className="text-muted-foreground">AI 精选高价值比赛</p>
                  </div>

                  {/* 只显示1场比赛 */}
                  <div className="max-w-2xl mx-auto mb-12">
                    {upcoming.filter((m) => m.has_value).slice(0, 1).map((match: any) => (
                      <MatchCard key={match.id} match={match} />
                    ))}
                  </div>

                  {/* Unlock VIP 提示 */}
                  <div className="max-w-2xl mx-auto">
                    <div className="bg-white/80 backdrop-blur-md rounded-2xl p-8 shadow-lg border border-white/40 text-center">
                      <div className="mb-6">
                        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-primary/10 mb-4">
                          <svg className="w-10 h-10 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                          </svg>
                        </div>
                        <h3 className="text-2xl font-bold text-foreground mb-3 font-[family-name:var(--font-heading)]">
                          解锁 60+ 高价值预测
                        </h3>
                        <p className="text-muted-foreground text-lg mb-2">
                          获取所有 AI 驱动的比赛预测
                        </p>
                        <p className="text-muted-foreground">
                          高级筛选 • 实时更新 • 专业洞察
                        </p>
                      </div>

                      <button
                        onClick={() => {
                          const loginBtn = document.querySelector('header button') as HTMLButtonElement;
                          loginBtn?.click();
                        }}
                        className="px-10 py-4 rounded-full bg-primary text-primary-foreground text-base font-bold hover:bg-primary/90 transition-all active:scale-95 shadow-lg"
                      >
                        加入会员 • 立即登录
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                /* 已登录 - 显示所有比赛 */
                <>
                  <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-2 gap-8 items-start">
                    {dateKeys.map((dateKey) => {
                      const dayMatches = grouped[dateKey];
                      return dayMatches.map((match: any) => (
                        <MatchCard key={match.id} match={match} />
                      ));
                    })}
                  </div>

                  {dateKeys.length === 0 && (
                    <div className="text-center py-32">
                      <p className="text-muted-foreground text-sm">暂无比赛数据</p>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </main>

      <footer className={`py-6 text-center text-xs text-muted-foreground/60 ${user ? 'pl-20 md:pl-64' : ''}`}>
        识机 · KINETIC · CatBoost RPS 0.1393
      </footer>

      {/* AI Chat Window */}
      <ChatWindow />
    </div>
  );
}
