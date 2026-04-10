"use client";

import { useState, useEffect } from "react";
import { NavBar } from "@/components/NavBar";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface SubscriptionStatus {
  has_access: boolean;
  subscription_type: string;
  plan_name: string;
  expires_at: string | null;
  days_remaining: number;
}

export default function AccountPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      router.push("/");
      return;
    }

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const token = localStorage.getItem("token");
    if (!token) return;

    fetch(`${API_BASE}/api/subscription/status?token=${token}`)
      .then((r) => r.json())
      .then((data) => {
        setSubscription(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [user, router]);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "未知";
    const date = new Date(dateStr);
    return date.toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" });
  };

  const getStatusBadge = (type: string) => {
    switch (type) {
      case "trial":
        return <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">试用中</span>;
      case "basic_yearly":
        return <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">基础档</span>;
      case "premium_yearly":
        return <span className="px-3 py-1 bg-amber-100 text-amber-700 rounded-full text-sm font-medium">高级档</span>;
      case "expired":
        return <span className="px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm font-medium">已过期</span>;
      default:
        return <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm font-medium">{type}</span>;
    }
  };

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      {/* Background */}
      <div className="stadium-bg" style={{
        backgroundImage: "url('https://lh3.googleusercontent.com/aida-public/AB6AXuAtRyOqo1KjYFfgZfMmI2w05md6_k8PnUOFCsHdV3mfjaVUoruyOmhvaeQnPy2wOj2faZlBV5G5c5_jUDL0jxQGLsPihXFAkI0Re_d2fRmr_SZ4dXptp29h3nzaFy_CpGjcMDTfIaPIzeE1Bb432o7sghdHWm-zb70tBKwBeAirc-pWx1d0hswDQYSLM61QySwpQQf4BjlDhNWNTZB9DE6weULN9xKDQPm_Tw-Ua1uVC5GRfJC4PPjJPXSIRl8t-bWJyXVCv9ad0CGG')",
      }}>
        <div className="absolute inset-0 bg-gradient-to-tr from-background via-background/40 to-transparent"></div>
      </div>

      <NavBar />

      <main className="pt-24 min-h-screen relative z-10">
        <div className="max-w-4xl mx-auto px-6 lg:px-12 py-16">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-2 font-[family-name:var(--font-heading)]">
              账户管理
            </h1>
            <p className="text-muted-foreground">管理你的订阅和个人信息</p>
          </div>

          {loading ? (
            <div className="bg-white/80 backdrop-blur-md rounded-xl p-8 shadow-sm border border-white/40">
              <p className="text-center text-muted-foreground">加载中...</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* 用户信息 */}
              <div className="bg-white/80 backdrop-blur-md rounded-xl p-8 shadow-sm border border-white/40">
                <h2 className="text-xl font-bold text-foreground mb-6 font-[family-name:var(--font-heading)]">
                  个人信息
                </h2>
                <div className="space-y-4">
                  <div className="flex items-center justify-between py-3 border-b border-border">
                    <span className="text-sm text-muted-foreground">用户名</span>
                    <span className="font-medium">{user.name}</span>
                  </div>
                  <div className="flex items-center justify-between py-3 border-b border-border">
                    <span className="text-sm text-muted-foreground">手机号</span>
                    <span className="font-medium">{user.phone}</span>
                  </div>
                </div>
              </div>

              {/* 订阅状态 */}
              <div className="bg-white/80 backdrop-blur-md rounded-xl p-8 shadow-sm border border-white/40">
                <h2 className="text-xl font-bold text-foreground mb-6 font-[family-name:var(--font-heading)]">
                  订阅状态
                </h2>
                {subscription ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between py-3 border-b border-border">
                      <span className="text-sm text-muted-foreground">套餐类型</span>
                      <span className="font-medium">{subscription.plan_name}</span>
                    </div>
                    <div className="flex items-center justify-between py-3 border-b border-border">
                      <span className="text-sm text-muted-foreground">当前状态</span>
                      {getStatusBadge(subscription.subscription_type)}
                    </div>
                    <div className="flex items-center justify-between py-3 border-b border-border">
                      <span className="text-sm text-muted-foreground">到期时间</span>
                      <span className="font-medium">{formatDate(subscription.expires_at)}</span>
                    </div>
                    <div className="flex items-center justify-between py-3">
                      <span className="text-sm text-muted-foreground">剩余天数</span>
                      <span className="font-medium text-primary">{subscription.days_remaining} 天</span>
                    </div>

                    {!subscription.has_access && (
                      <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
                        <p className="text-sm text-red-700 mb-3">
                          你的订阅已过期，请续费以继续使用完整功能
                        </p>
                        <Link
                          href="/pricing"
                          className="inline-block px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
                        >
                          立即续费
                        </Link>
                      </div>
                    )}

                    {subscription.subscription_type === "trial" && subscription.days_remaining < 7 && (
                      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                        <p className="text-sm text-blue-700 mb-3">
                          你的试用期即将结束，升级订阅以继续享受服务
                        </p>
                        <Link
                          href="/pricing"
                          className="inline-block px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
                        >
                          查看套餐
                        </Link>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">无法加载订阅信息</p>
                )}
              </div>

              {/* 操作按钮 */}
              <div className="bg-white/80 backdrop-blur-md rounded-xl p-8 shadow-sm border border-white/40">
                <button
                  onClick={() => {
                    logout();
                    router.push("/");
                  }}
                  className="w-full px-6 py-3 bg-red-500 text-white rounded-lg font-medium hover:bg-red-600 transition-colors"
                >
                  退出登录
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
