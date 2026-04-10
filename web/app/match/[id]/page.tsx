"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { ChatWindow } from "@/components/ChatWindow";
import Image from "next/image";
import { getTeamLogo } from "@/lib/teamLogos";

const LEAGUE_CN: Record<string, string> = {
  PL: "英超", ELC: "英冠", SA: "意甲", PD: "西甲",
  BL1: "德甲", FL1: "法甲", CL: "欧冠", EL: "欧联", PPL: "葡超", DED: "荷甲",
};

const RESULT_CN: Record<string, { label: string; color: string; bg: string }> = {
  W: { label: "胜", color: "text-white", bg: "bg-gradient-to-br from-emerald-400 to-emerald-600 shadow-sm shadow-emerald-200" },
  D: { label: "平", color: "text-white", bg: "bg-gradient-to-br from-amber-300 to-amber-500 shadow-sm shadow-amber-200" },
  L: { label: "负", color: "text-white", bg: "bg-gradient-to-br from-rose-400 to-rose-600 shadow-sm shadow-rose-200" },
};

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl bg-white shadow-sm overflow-hidden ${className}`}>
      {children}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="text-xl font-bold mb-8 text-[#1b1b23]" style={{ fontFamily: 'Manrope, sans-serif' }}>{children}</h3>;
}

function ProbGauge({ label, pred, implied }: { label: string; pred: number; implied: number }) {
  const value = pred - implied;
  const hasValue = value > 0.03;
  const pct = Math.round(pred * 100);
  return (
    <div className="flex flex-col items-center gap-3">
      <div className="text-slate-500 font-bold text-sm" style={{ fontFamily: 'Inter, sans-serif' }}>{label}</div>
      <div className="text-4xl font-black text-[#3f3bbd]" style={{ fontFamily: 'Manrope, sans-serif' }}>
        {pct}<span className="text-xl">%</span>
      </div>
      <div className="w-full h-3 bg-[#f0ecf8] rounded-full overflow-hidden">
        <div
          className="h-full bg-[#3f3bbd] rounded-full transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function StatBar({ label, homeVal, awayVal, format = (v: number) => String(v) }: {
  label: string; homeVal: number; awayVal: number; format?: (v: number) => string;
}) {
  const total = homeVal + awayVal || 1;
  const homePct = homeVal / total;
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs font-bold items-center">
        <span className="text-[#3f3bbd] tabular-nums" style={{ fontFamily: 'Manrope, sans-serif' }}>{format(homeVal)}</span>
        <span className="text-slate-400 font-medium" style={{ fontFamily: 'Inter, sans-serif' }}>{label}</span>
        <span className="text-[#5a598b] tabular-nums" style={{ fontFamily: 'Manrope, sans-serif' }}>{format(awayVal)}</span>
      </div>
      <div className="flex h-2 w-full rounded-full overflow-hidden bg-slate-100">
        <div className="bg-[#5856d6] transition-all duration-700" style={{ width: `${homePct * 100}%` }} />
        <div className="bg-[#c8c7ff] transition-all duration-700" style={{ width: `${(1 - homePct) * 100}%` }} />
      </div>
    </div>
  );
}

export default function MatchDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [homeLogoError, setHomeLogoError] = useState(false);
  const [awayLogoError, setAwayLogoError] = useState(false);

  useEffect(() => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${API_BASE}/api/match/${id}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!data || data.error) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-3">
      <p className="text-muted-foreground">比赛数据不存在</p>
      <Link href="/" className="text-xs text-blue-400 hover:underline">返回首页</Link>
    </div>
  );

  const { match, prediction, features, h2h, home_form, away_form, media_analysis } = data;
  const isFinished = match.home_goals !== null;
  const leagueName = match.league_cn || LEAGUE_CN[match.league] || match.league || "友谊赛";
  const matchDate = new Date(match.date);

  const homeLogo = getTeamLogo(match.home_team);
  const awayLogo = getTeamLogo(match.away_team);

  return (
    <div className="min-h-screen bg-[#fcf8ff] pb-12">
      {/* Top Navigation Bar */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-xl shadow-sm shadow-slate-200/50">
        <div className="flex justify-between items-center px-6 py-4 max-w-screen-2xl mx-auto">
          <div className="flex items-center gap-4">
            <Link href="/" className="p-2 hover:bg-slate-100 rounded-full transition-colors">
              <ArrowLeft className="w-5 h-5 text-slate-900" />
            </Link>
            <span className="text-xl font-bold tracking-tighter text-slate-900" style={{ fontFamily: 'Manrope, sans-serif' }}>
              Augur · 识机
            </span>
          </div>
        </div>
      </nav>

      <main className="pt-24 px-4 md:px-8 max-w-5xl mx-auto space-y-8">
        {/* Match Header */}
        <header className="bg-white rounded-xl p-8 md:p-12 text-center relative overflow-hidden shadow-sm">
          <div className="relative z-10 space-y-6">
            <div className="flex flex-col items-center gap-2">
              <div className="inline-flex items-center gap-2 bg-[#e2dfff] text-[#3631b4] px-4 py-1.5 rounded-full text-xs font-bold tracking-widest uppercase" style={{ fontFamily: 'Inter, sans-serif' }}>
                {leagueName} {isFinished && "• 已完赛"}
              </div>
              {!isFinished && (
                <div className="text-sm text-slate-500 font-medium" style={{ fontFamily: 'Inter, sans-serif' }}>
                  {matchDate.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })} {matchDate.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </div>
              )}
            </div>

            <div className="flex flex-col md:flex-row items-center justify-between gap-8 py-4">
              {/* Home Team */}
              <div className="flex-1 flex flex-col items-center md:items-end gap-4">
                {!homeLogoError && homeLogo ? (
                  <Image
                    src={homeLogo}
                    alt={match.home_team}
                    width={80}
                    height={80}
                    className="object-contain"
                    onError={() => setHomeLogoError(true)}
                  />
                ) : (
                  <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[#5856d6] to-[#3f3bbd] flex items-center justify-center">
                    <span className="text-2xl font-black text-white" style={{ fontFamily: 'Manrope, sans-serif' }}>
                      {(match.home_team_cn || match.home_team).slice(0, 2)}
                    </span>
                  </div>
                )}
                <h2 className="text-2xl font-extrabold tracking-tight text-[#1b1b23]" style={{ fontFamily: 'Manrope, sans-serif' }}>
                  {match.home_team_cn || match.home_team}
                </h2>
              </div>

              {/* Score/Time */}
              <div className="flex flex-col items-center justify-center gap-2">
                {isFinished ? (
                  <div className="text-5xl font-black tracking-tighter text-[#3f3bbd]" style={{ fontFamily: 'Manrope, sans-serif' }}>
                    {match.home_goals} - {match.away_goals}
                  </div>
                ) : (
                  <>
                    <div className="text-5xl font-black tracking-tighter text-[#3f3bbd]" style={{ fontFamily: 'Manrope, sans-serif' }}>
                      VS
                    </div>
                    {prediction && prediction.pred_score_home !== undefined && prediction.pred_score_away !== undefined && (
                      <div className="text-sm text-slate-400 font-medium" style={{ fontFamily: 'Inter, sans-serif' }}>
                        预测比分 {prediction.pred_score_home} - {prediction.pred_score_away}
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Away Team */}
              <div className="flex-1 flex flex-col items-center md:items-start gap-4">
                {!awayLogoError && awayLogo ? (
                  <Image
                    src={awayLogo}
                    alt={match.away_team}
                    width={80}
                    height={80}
                    className="object-contain"
                    onError={() => setAwayLogoError(true)}
                  />
                ) : (
                  <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[#c8c7ff] to-[#5a598b] flex items-center justify-center">
                    <span className="text-2xl font-black text-white" style={{ fontFamily: 'Manrope, sans-serif' }}>
                      {(match.away_team_cn || match.away_team).slice(0, 2)}
                    </span>
                  </div>
                )}
                <h2 className="text-2xl font-extrabold tracking-tight text-[#1b1b23]" style={{ fontFamily: 'Manrope, sans-serif' }}>
                  {match.away_team_cn || match.away_team}
                </h2>
              </div>
            </div>
          </div>
        </header>

        {/* Bento Grid Analysis */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
          {/* AI Prediction Center */}
          {prediction && (
            <section className="md:col-span-8 bg-white rounded-xl p-8 shadow-sm">
              <div className="flex items-center justify-between mb-10">
                <SectionTitle>AI 模型预测</SectionTitle>
                <div className="px-4 py-1 bg-[#f5f2fd] rounded-full text-xs font-semibold text-slate-500" style={{ fontFamily: 'Inter, sans-serif' }}>
                  置信度: {Math.round(Math.max(prediction.pred_home, prediction.pred_draw, prediction.pred_away) * 100)}%
                </div>
              </div>
              <div className="grid grid-cols-3 gap-6 relative">
                <ProbGauge label="主胜 (3)" pred={prediction.pred_home} implied={prediction.implied_home} />
                <ProbGauge label="平局 (1)" pred={prediction.pred_draw} implied={prediction.implied_draw} />
                <ProbGauge label="客胜 (0)" pred={prediction.pred_away} implied={prediction.implied_away} />
              </div>
              {prediction?.ai_explanation ? (
                <div className="mt-10 p-6 bg-[#e2dfff] rounded-lg flex items-start gap-4">
                  <span className="text-2xl">💡</span>
                  <p className="text-[#3631b4] text-sm leading-relaxed font-medium" style={{ fontFamily: 'Inter, sans-serif' }}>
                    {prediction.ai_explanation}
                  </p>
                </div>
              ) : (
                <div className="mt-10 p-6 bg-[#f5f2fd] rounded-lg flex items-start gap-4">
                  <span className="text-2xl">🤖</span>
                  <p className="text-slate-500 text-sm leading-relaxed font-medium" style={{ fontFamily: 'Inter, sans-serif' }}>
                    AI 预测说明正在生成中，请稍后刷新查看详细分析...
                  </p>
                </div>
              )}
            </section>
          )}

          {/* Market Odds */}
          {match.odds_home && (
            <section className="md:col-span-4 bg-white rounded-xl p-8 shadow-sm">
              <SectionTitle>市场赔率</SectionTitle>
              <div className="space-y-6">
                <div className="flex justify-between items-center p-4 bg-[#f5f2fd] rounded-lg">
                  <span className="font-bold text-slate-500" style={{ fontFamily: 'Inter, sans-serif' }}>主胜</span>
                  <span className="font-black text-xl text-[#3f3bbd]" style={{ fontFamily: 'Manrope, sans-serif' }}>{match.odds_home?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center p-4 bg-[#f5f2fd] rounded-lg">
                  <span className="font-bold text-slate-500" style={{ fontFamily: 'Inter, sans-serif' }}>平局</span>
                  <span className="font-black text-xl" style={{ fontFamily: 'Manrope, sans-serif' }}>{match.odds_draw?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center p-4 bg-[#f5f2fd] rounded-lg">
                  <span className="font-bold text-slate-500" style={{ fontFamily: 'Inter, sans-serif' }}>客胜</span>
                  <span className="font-black text-xl" style={{ fontFamily: 'Manrope, sans-serif' }}>{match.odds_away?.toFixed(2)}</span>
                </div>
                <p className="text-[11px] text-slate-400 text-center px-4" style={{ fontFamily: 'Inter, sans-serif' }}>
                  数据来源于主流博彩机构平均初赔
                </p>
              </div>
            </section>
          )}

          {/* Strength Balance */}
          {features && (
            <section className="md:col-span-6 bg-white rounded-xl p-8 shadow-sm">
              <SectionTitle>实力对比</SectionTitle>
              <div className="space-y-8">
                <StatBar label="进攻评分" homeVal={features.pi_attack_home} awayVal={features.pi_attack_away} format={v => v.toFixed(1)} />
                <StatBar label="防守评分" homeVal={features.pi_defense_home} awayVal={features.pi_defense_away} format={v => v.toFixed(1)} />
                <StatBar label="近5场胜率" homeVal={features.win_rate_home_5} awayVal={features.win_rate_away_5} format={v => `${Math.round(v * 100)}%`} />
                <StatBar label="近5场场均进球" homeVal={features.goals_scored_home_5} awayVal={features.goals_scored_away_5} format={v => v.toFixed(1)} />
              </div>
              <div className="mt-8 flex justify-between items-center text-[10px] font-bold text-slate-400 uppercase tracking-widest" style={{ fontFamily: 'Inter, sans-serif' }}>
                <span>{match.home_team_cn || match.home_team}</span>
                <span>实力差值 {features.pi_diff > 0 ? "+" : ""}{features.pi_diff.toFixed(1)}</span>
                <span>{match.away_team_cn || match.away_team}</span>
              </div>
            </section>
          )}

          {/* Recent Form */}
          <section className="md:col-span-6 bg-white rounded-xl p-8 shadow-sm">
            <SectionTitle>近期战绩</SectionTitle>
            {(home_form?.length > 0 || away_form?.length > 0) ? (
              <div className="space-y-8">
                {/* Home Team */}
                {home_form?.length > 0 && (
                  <div className="flex items-center justify-between gap-6">
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-sm" style={{ fontFamily: 'Inter, sans-serif' }}>{match.home_team_cn || match.home_team}</span>
                    </div>
                    <div className="flex gap-2">
                      {home_form.slice(0, 5).map((f: any, i: number) => {
                        const r = RESULT_CN[f.result] ?? { label: f.result, color: "text-white", bg: "bg-slate-400" };
                        return (
                          <div key={i} className={`w-8 h-8 rounded-lg ${r.bg} ${r.color} flex items-center justify-center text-[10px] font-bold`}>
                            {r.label}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                {/* Away Team */}
                {away_form?.length > 0 && (
                  <div className="flex items-center justify-between gap-6">
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-sm" style={{ fontFamily: 'Inter, sans-serif' }}>{match.away_team_cn || match.away_team}</span>
                    </div>
                    <div className="flex gap-2">
                      {away_form.slice(0, 5).map((f: any, i: number) => {
                        const r = RESULT_CN[f.result] ?? { label: f.result, color: "text-white", bg: "bg-slate-400" };
                        return (
                          <div key={i} className={`w-8 h-8 rounded-lg ${r.bg} ${r.color} flex items-center justify-center text-[10px] font-bold`}>
                            {r.label}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 bg-[#f5f2fd] rounded-xl text-center">
                <div className="text-4xl mb-4">📊</div>
                <p className="text-slate-500 text-sm font-medium" style={{ fontFamily: 'Inter, sans-serif' }}>
                  暂无近期战绩数据
                </p>
              </div>
            )}
          </section>

          {/* H2H */}
          <section className="md:col-span-12 bg-white rounded-xl p-8 shadow-sm">
            <SectionTitle>历史交锋</SectionTitle>
            {h2h && h2h.total > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[11px] text-slate-400 font-bold uppercase tracking-widest border-b border-slate-100">
                      <th className="pb-4 text-left" style={{ fontFamily: 'Inter, sans-serif' }}>日期</th>
                      <th className="pb-4 text-center" style={{ fontFamily: 'Inter, sans-serif' }}>比分</th>
                      <th className="pb-4 text-right" style={{ fontFamily: 'Inter, sans-serif' }}>结果</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {h2h.recent?.map((r: any, i: number) => {
                      const homeWin = r.home_goals > r.away_goals;
                      const draw = r.home_goals === r.away_goals;
                      const awayWin = r.away_goals > r.home_goals;
                      return (
                        <tr key={i} className="hover:bg-slate-50/50 transition-colors">
                          <td className="py-5 text-slate-500 font-medium" style={{ fontFamily: 'Inter, sans-serif' }}>
                            {new Date(r.date).toLocaleDateString('zh-CN')}
                          </td>
                          <td className="py-5 text-center">
                            <span className="font-extrabold text-lg tracking-tight text-slate-900" style={{ fontFamily: 'Manrope, sans-serif' }}>
                              {r.home_goals} : {r.away_goals}
                            </span>
                          </td>
                          <td className="py-5 text-right">
                            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full ${
                              homeWin ? 'bg-emerald-50' : draw ? 'bg-slate-100' : 'bg-rose-50'
                            }`}>
                              <div className={`w-1.5 h-1.5 rounded-full ${
                                homeWin ? 'bg-emerald-500' : draw ? 'bg-slate-400' : 'bg-rose-500'
                              }`}></div>
                              <span className={`font-bold text-xs ${
                                homeWin ? 'text-emerald-600' : draw ? 'text-slate-500' : 'text-rose-600'
                              }`} style={{ fontFamily: 'Inter, sans-serif' }}>
                                {homeWin ? '胜' : draw ? '平' : '负'}
                              </span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 bg-[#f5f2fd] rounded-xl text-center">
                <div className="text-4xl mb-4">⚔️</div>
                <p className="text-slate-500 text-sm font-medium" style={{ fontFamily: 'Inter, sans-serif' }}>
                  暂无历史交锋数据
                </p>
              </div>
            )}
          </section>

          {/* Media Analysis */}
          <section className="md:col-span-12 bg-white rounded-xl p-8 shadow-sm">
            <SectionTitle>媒体预测</SectionTitle>
            {media_analysis ? (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="p-6 bg-[#f5f2fd] rounded-xl">
                    <div className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3" style={{ fontFamily: 'Inter, sans-serif' }}>
                      媒体倾向
                    </div>
                    <div className="text-2xl font-black text-[#3f3bbd]" style={{ fontFamily: 'Manrope, sans-serif' }}>
                      {media_analysis.sentiment || "中性"}
                    </div>
                  </div>
                  <div className="p-6 bg-[#f5f2fd] rounded-xl">
                    <div className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3" style={{ fontFamily: 'Inter, sans-serif' }}>
                      热度指数
                    </div>
                    <div className="text-2xl font-black text-[#3f3bbd]" style={{ fontFamily: 'Manrope, sans-serif' }}>
                      {media_analysis.heat_index || "N/A"}
                    </div>
                  </div>
                  <div className="p-6 bg-[#f5f2fd] rounded-xl">
                    <div className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3" style={{ fontFamily: 'Inter, sans-serif' }}>
                      数据来源
                    </div>
                    <div className="text-2xl font-black text-[#3f3bbd]" style={{ fontFamily: 'Manrope, sans-serif' }}>
                      {media_analysis.sources || "0"}
                    </div>
                  </div>
                </div>
                {media_analysis.summary && (
                  <div className="p-6 bg-[#fcf8ff] rounded-xl">
                    <p className="text-sm text-[#464554] leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                      {media_analysis.summary}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 bg-[#f5f2fd] rounded-xl text-center">
                <div className="text-4xl mb-4">📰</div>
                <p className="text-slate-500 text-sm font-medium" style={{ fontFamily: 'Inter, sans-serif' }}>
                  媒体舆情分析正在生成中，请稍后刷新查看
                </p>
              </div>
            )}
          </section>
        </div>
      </main>

      {/* AI Chat Window */}
      {match && (
        <ChatWindow
          matchId={match.id}
          matchContext={{
            homeTeam: match.home_team,
            awayTeam: match.away_team,
            league: LEAGUE_CN[match.league] || match.league,
            predHome: match.pred_home_win,
            predDraw: match.pred_draw,
            predAway: match.pred_away_win,
          }}
        />
      )}
    </div>
  );
}
