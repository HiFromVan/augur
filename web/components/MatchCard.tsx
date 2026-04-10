"use client";

import Link from "next/link";
import Image from "next/image";
import { useState } from "react";
import { getTeamLogo } from "@/lib/teamLogos";

const LEAGUE_CN: Record<string, string> = {
  PL: "英超", ELC: "英冠", SA: "意甲", PD: "西甲",
  BL1: "德甲", FL1: "法甲", CL: "欧冠", EL: "欧联",
  PPL: "葡超", DED: "荷甲",
};

const LEAGUE_COLOR: Record<string, string> = {
  PL: "#5856d6", ELC: "#f97316", SA: "#3b82f6",
  PD: "#ef4444", BL1: "#dc2626", FL1: "#60a5fa",
  CL: "#eab308", EL: "#fb923c", PPL: "#22c55e", DED: "#f97316",
};

interface MatchCardProps {
  match: any;
}

function formatTime(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
}

export function MatchCard({ match }: MatchCardProps) {
  const league = match.league ?? "";
  const leagueName = match.league_cn ?? LEAGUE_CN[league] ?? league;
  const leagueColor = LEAGUE_COLOR[league] ?? "#5856d6";
  const isFinished = match.home_goals !== null;
  const predHome = match.pred_home ?? 0;
  const predDraw = match.pred_draw ?? 0;
  const predAway = match.pred_away ?? 0;
  const hasValue = match.has_value;

  const homeTeamName = match.home_team_cn || match.home_team;
  const awayTeamName = match.away_team_cn || match.away_team;
  const homeLogo = getTeamLogo(match.home_team);
  const awayLogo = getTeamLogo(match.away_team);

  const [homeLogoError, setHomeLogoError] = useState(false);
  const [awayLogoError, setAwayLogoError] = useState(false);

  const vh = ((match.value_home ?? 0) * 100);
  const vd = ((match.value_draw ?? 0) * 100);
  const va = ((match.value_away ?? 0) * 100);

  // 生成AI预测说明
  const getPredictionReason = () => {
    if (isFinished) return null;

    // 优先使用AI生成的说明
    if (match.ai_explanation) {
      return match.ai_explanation;
    }

    // 降级方案：生成简单说明
    const homeWinProb = Math.round(predHome * 100);
    const drawProb = Math.round(predDraw * 100);
    const awayWinProb = Math.round(predAway * 100);

    let reason = "基于";
    const factors = [];

    // 判断主要预测结果
    if (homeWinProb > drawProb && homeWinProb > awayWinProb) {
      reason = `预测${homeTeamName}获胜，`;
      if (homeWinProb > 50) {
        factors.push("主场优势明显");
      }
    } else if (awayWinProb > drawProb && awayWinProb > homeWinProb) {
      reason = `预测${awayTeamName}客场取胜，`;
      if (awayWinProb > 45) {
        factors.push("客队实力占优");
      }
    } else {
      reason = "双方实力接近，";
      factors.push("平局可能性较大");
    }

    // 添加其他因素
    if (match.expected_goals_home && match.expected_goals_away) {
      const goalDiff = Math.abs(match.expected_goals_home - match.expected_goals_away);
      if (goalDiff < 0.5) {
        factors.push("预期进球数相近");
      } else if (goalDiff > 1.5) {
        factors.push("进攻火力差距明显");
      }
    }

    if (factors.length === 0) {
      factors.push("综合历史数据与当前状态分析");
    }

    return reason + factors.join("，");
  };

  const predictionReason = getPredictionReason();

  return (
    <Link href={`/match/${match.id}`}>
      <div className="group relative bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-white/40 hover:shadow-xl transition-all duration-500 transform hover:-translate-y-1 cursor-pointer">
        {/* League + Status */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <span className="text-[10px] font-bold tracking-widest uppercase" style={{ color: leagueColor }}>
              {leagueName}
            </span>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs font-semibold text-muted-foreground">
                {isFinished ? "终场" : formatTime(match.date)}
              </span>
            </div>
          </div>
          {hasValue && !isFinished && (
            <div className="flex items-center gap-1.5 bg-primary/10 px-3 py-1 rounded-full">
              <span className="text-[10px] font-bold text-primary tracking-tight">高价值</span>
            </div>
          )}
        </div>

        {/* Teams + Score */}
        <div className="flex items-center justify-between gap-6 mb-6">
          {/* Home Team */}
          <div className="flex-1 flex items-center justify-end gap-3">
            <p className="font-bold text-lg leading-tight text-right">{homeTeamName}</p>
            {homeLogo && !homeLogoError && (
              <div className="relative w-10 h-10 flex-shrink-0">
                <Image
                  src={homeLogo}
                  alt={homeTeamName}
                  fill
                  className="object-contain"
                  unoptimized
                  onError={() => setHomeLogoError(true)}
                />
              </div>
            )}
          </div>

          {/* Score/Prediction */}
          <div className="flex items-center gap-3">
            {isFinished ? (
              <>
                <span className={`text-3xl font-bold tabular-nums ${match.home_goals > match.away_goals ? "text-primary" : "text-muted-foreground"}`}>
                  {match.home_goals}
                </span>
                <span className="text-2xl font-bold text-muted-foreground">-</span>
                <span className={`text-3xl font-bold tabular-nums ${match.away_goals > match.home_goals ? "text-primary" : "text-muted-foreground"}`}>
                  {match.away_goals}
                </span>
              </>
            ) : (
              <span className="text-sm text-muted-foreground">VS</span>
            )}
          </div>

          {/* Away Team */}
          <div className="flex-1 flex items-center justify-start gap-3">
            {awayLogo && !awayLogoError && (
              <div className="relative w-10 h-10 flex-shrink-0">
                <Image
                  src={awayLogo}
                  alt={awayTeamName}
                  fill
                  className="object-contain"
                  unoptimized
                  onError={() => setAwayLogoError(true)}
                />
              </div>
            )}
            <p className="font-bold text-lg leading-tight text-left">{awayTeamName}</p>
          </div>
        </div>

        {/* Probabilities */}
        {predHome > 0 && !isFinished && (
          <div className="flex items-center justify-between gap-4 pt-4 border-t border-border">
            <div className="flex-1 text-center">
              <div className="text-[10px] font-bold text-muted-foreground mb-1">主胜</div>
              <div className="text-base font-bold" style={{ color: leagueColor }}>
                {Math.round(predHome * 100)}%
              </div>
            </div>
            <div className="flex-1 text-center">
              <div className="text-[10px] font-bold text-muted-foreground mb-1">平局</div>
              <div className="text-base font-bold text-slate-500">
                {Math.round(predDraw * 100)}%
              </div>
            </div>
            <div className="flex-1 text-center">
              <div className="text-[10px] font-bold text-muted-foreground mb-1">客胜</div>
              <div className="text-base font-bold text-rose-500">
                {Math.round(predAway * 100)}%
              </div>
            </div>
          </div>
        )}

        {/* Value indicator */}
        {predictionReason && (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs text-muted-foreground leading-relaxed">
              💡 {predictionReason}
            </p>
          </div>
        )}
      </div>
    </Link>
  );
}
