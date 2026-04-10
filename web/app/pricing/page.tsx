"use client";

import { useState, useEffect } from "react";
import { NavBar } from "@/components/NavBar";
import { useAuth } from "@/contexts/AuthContext";

interface Plan {
  plan_code: string;
  name: string;
  price: number;
  duration_days: number;
  description: string;
  features?: {
    ai_chat?: boolean;
    ai_chat_daily_limit?: number;
    media_analysis?: boolean;
    advanced_filters?: boolean;
    export_data?: boolean;
    api_access?: boolean;
    portfolio_tracking?: boolean;
    advanced_analytics?: boolean;
    priority_support?: boolean;
    [key: string]: any;
  };
}

export default function PricingPage() {
  const { user } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const API_BASE = typeof window !== 'undefined' && window.location.hostname.includes('trycloudflare.com')
      ? "https://fee-lease-equal-fisheries.trycloudflare.com"
      : "http://localhost:8000";

    fetch(`${API_BASE}/api/subscription/plans`)
      .then((r) => r.json())
      .then((data) => {
        setPlans(data.plans || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const formatPrice = (price: number) => {
    return (price / 100).toFixed(0);
  };

  const getMonthlyPrice = (price: number, days: number) => {
    return ((price / 100) / (days / 30)).toFixed(0);
  };

  return (
    <div className="min-h-screen bg-[#fcf8ff]">
      <NavBar />

      {/* Hero Section */}
      <div className="relative pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl md:text-6xl font-bold text-[#1b1b23] mb-6 tracking-tight" style={{ fontFamily: 'Manrope, sans-serif' }}>
            选择适合你的套餐
          </h1>
          <p className="text-lg text-[#464554] max-w-2xl mx-auto" style={{ fontFamily: 'Inter, sans-serif' }}>
            AI 驱动的足球预测，助你做出更明智的决策
          </p>
        </div>
      </div>

      {/* Pricing Cards */}
      <div className="max-w-7xl mx-auto px-6 pb-16">
        {loading ? (
          <div className="text-center py-20">
            <div className="inline-block w-8 h-8 border-3 border-[#3f3bbd] border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 max-w-5xl mx-auto">
            {plans.map((plan) => {
              const isPremium = plan.plan_code === 'premium_yearly';

              return (
                <div
                  key={plan.plan_code}
                  className={`relative rounded-3xl p-10 transition-all duration-500 hover:-translate-y-2 ${
                    isPremium
                      ? 'bg-white shadow-[0_20px_60px_rgba(63,59,189,0.15)] border-2 border-[#3f3bbd]/20'
                      : 'bg-[#f5f2fd] shadow-[0_10px_40px_rgba(27,27,35,0.06)]'
                  }`}
                  style={{
                    backdropFilter: 'blur(20px)',
                  }}
                >
                  {isPremium && (
                    <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                      <div className="bg-gradient-to-r from-[#3f3bbd] to-[#5856d6] text-white px-6 py-2 rounded-full text-sm font-bold shadow-lg" style={{ fontFamily: 'Inter, sans-serif' }}>
                        推荐方案
                      </div>
                    </div>
                  )}

                  {/* Plan Header */}
                  <div className="mb-8">
                    <h3 className="text-2xl font-bold text-[#1b1b23] mb-3" style={{ fontFamily: 'Manrope, sans-serif' }}>
                      {plan.name}
                    </h3>
                    <p className="text-sm text-[#777585] leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                      {plan.description}
                    </p>
                  </div>

                  {/* Price */}
                  <div className="mb-10">
                    <div className="flex items-baseline gap-2 mb-2">
                      <span className="text-6xl font-bold text-[#1b1b23] tracking-tight" style={{ fontFamily: 'Manrope, sans-serif' }}>
                        ¥{formatPrice(plan.price)}
                      </span>
                      <span className="text-lg text-[#777585]" style={{ fontFamily: 'Inter, sans-serif' }}>/年</span>
                    </div>
                    <p className="text-sm text-[#777585]" style={{ fontFamily: 'Inter, sans-serif' }}>
                      平均 ¥{getMonthlyPrice(plan.price, plan.duration_days)}/月
                    </p>
                  </div>

                  {/* CTA Button */}
                  <button
                    onClick={() => {
                      if (!user) {
                        window.location.href = '/login';
                        return;
                      }
                      window.location.href = `/checkout?plan=${plan.plan_code}`;
                    }}
                    className={`w-full py-4 rounded-2xl font-semibold text-base transition-all duration-300 ${
                      isPremium
                        ? 'bg-gradient-to-r from-[#3f3bbd] to-[#5856d6] text-white shadow-[0_10px_30px_rgba(63,59,189,0.3)] hover:shadow-[0_15px_40px_rgba(63,59,189,0.4)] hover:scale-[1.02]'
                        : 'bg-[#e4e1ec] text-[#1b1b23] hover:bg-[#dcd8e4]'
                    }`}
                    style={{ fontFamily: 'Inter, sans-serif' }}
                  >
                    {user ? '立即订阅' : '登录后订阅'}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Features Comparison Table */}
        <div className="max-w-5xl mx-auto mt-20">
          <h2 className="text-3xl font-bold text-[#1b1b23] text-center mb-12" style={{ fontFamily: 'Manrope, sans-serif' }}>
            权益对比
          </h2>

          <div className="bg-white rounded-3xl shadow-[0_10px_40px_rgba(27,27,35,0.06)] overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-[#f5f2fd]">
                  <th className="text-left py-6 px-8 text-sm font-bold text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    功能权益
                  </th>
                  <th className="text-center py-6 px-8 text-sm font-bold text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    基础档
                  </th>
                  <th className="text-center py-6 px-8 text-sm font-bold text-[#3f3bbd]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    高级档
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e4e1ec]">
                {/* 基础功能 */}
                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    查看比赛预测
                  </td>
                  <td className="py-5 px-8 text-center">
                    <div className="flex flex-col items-center gap-1">
                      <svg className="w-5 h-5 text-[#3f3bbd]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                      <span className="text-xs text-[#777585]" style={{ fontFamily: 'Inter, sans-serif' }}>10场/天</span>
                    </div>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <div className="flex flex-col items-center gap-1">
                      <svg className="w-5 h-5 text-[#3f3bbd]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                      <span className="text-xs text-[#777585]" style={{ fontFamily: 'Inter, sans-serif' }}>无限制</span>
                    </div>
                  </td>
                </tr>

                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    五大联赛覆盖
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#3f3bbd] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#3f3bbd] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                </tr>

                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    历史数据查询
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#3f3bbd] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#3f3bbd] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                </tr>

                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    AI 预测说明
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#3f3bbd] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#3f3bbd] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                </tr>

                {/* AI 功能 */}
                <tr className="bg-[#fcf8ff]">
                  <td className="py-5 px-8 text-sm text-[#1b1b23] font-semibold" style={{ fontFamily: 'Inter, sans-serif' }}>
                    AI 对话助手
                  </td>
                  <td className="py-5 px-8 text-center">
                    <div className="flex flex-col items-center gap-1">
                      <svg className="w-5 h-5 text-[#3f3bbd]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                      <span className="text-xs text-[#777585]" style={{ fontFamily: 'Inter, sans-serif' }}>5次/天</span>
                      <span className="text-xs text-[#777585]" style={{ fontFamily: 'Inter, sans-serif' }}>500 tokens/次</span>
                    </div>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <div className="flex flex-col items-center gap-1">
                      <svg className="w-5 h-5 text-[#7e3e00]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                      <span className="text-xs text-[#777585]" style={{ fontFamily: 'Inter, sans-serif' }}>50次/天</span>
                      <span className="text-xs text-[#777585]" style={{ fontFamily: 'Inter, sans-serif' }}>2000 tokens/次</span>
                    </div>
                  </td>
                </tr>

                {/* 高级功能 */}
                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    媒体舆情分析
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#c7c4d6] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#7e3e00] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                </tr>

                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    高级筛选功能
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#c7c4d6] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#7e3e00] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                </tr>

                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    数据导出
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#c7c4d6] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#7e3e00] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                </tr>

                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    投注组合跟踪
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#c7c4d6] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#7e3e00] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                </tr>

                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    高级分析报告
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#c7c4d6] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#7e3e00] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                </tr>

                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    API 访问
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#c7c4d6] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#7e3e00] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                </tr>

                <tr>
                  <td className="py-5 px-8 text-sm text-[#1b1b23]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    优先客服支持
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#c7c4d6] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </td>
                  <td className="py-5 px-8 text-center">
                    <svg className="w-5 h-5 text-[#7e3e00] mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* FAQ Section */}
        <div className="max-w-3xl mx-auto mt-32">
          <h2 className="text-3xl font-bold text-[#1b1b23] text-center mb-12" style={{ fontFamily: 'Manrope, sans-serif' }}>
            常见问题
          </h2>
          <div className="space-y-6">
            <div className="bg-white rounded-2xl p-8 shadow-[0_10px_40px_rgba(27,27,35,0.06)]">
              <h3 className="text-lg font-semibold text-[#1b1b23] mb-3" style={{ fontFamily: 'Manrope, sans-serif' }}>
                如何取消订阅？
              </h3>
              <p className="text-sm text-[#777585] leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                您可以随时在账户设置中取消订阅。取消后，您仍可使用服务直到当前订阅期结束。
              </p>
            </div>
            <div className="bg-white rounded-2xl p-8 shadow-[0_10px_40px_rgba(27,27,35,0.06)]">
              <h3 className="text-lg font-semibold text-[#1b1b23] mb-3" style={{ fontFamily: 'Manrope, sans-serif' }}>
                支持哪些支付方式？
              </h3>
              <p className="text-sm text-[#777585] leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                我们支持支付宝、微信支付等主流支付方式。
              </p>
            </div>
            <div className="bg-white rounded-2xl p-8 shadow-[0_10px_40px_rgba(27,27,35,0.06)]">
              <h3 className="text-lg font-semibold text-[#1b1b23] mb-3" style={{ fontFamily: 'Manrope, sans-serif' }}>
                可以升级套餐吗？
              </h3>
              <p className="text-sm text-[#777585] leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                可以。升级后，系统会自动计算剩余时长并调整价格。
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
