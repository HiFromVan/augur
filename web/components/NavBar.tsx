"use client";

import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { UserAvatar } from "@/components/UserAvatar";
import { LoginModal } from "@/components/LoginModal";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavBar() {
  const { user, logout } = useAuth();
  const [showMenu, setShowMenu] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const pathname = usePathname();

  const isActive = (path: string) => pathname === path;

  return (
    <>
      <header className="fixed top-0 w-full z-50 bg-background/80 backdrop-blur-md border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          {/* Logo */}
          <Link
            href="/"
            className="text-xl font-bold tracking-tight text-primary font-[family-name:var(--font-heading)] hover:opacity-80 transition-opacity"
          >
            识机
          </Link>

          {/* 居中菜单 */}
          <nav className="absolute left-1/2 -translate-x-1/2 flex items-center gap-8">
            <Link
              href="/"
              className={`text-sm font-medium transition-colors ${
                isActive("/")
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              预测
            </Link>

            <Link
              href="/history"
              className={`text-sm font-medium transition-colors ${
                isActive("/history")
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              历史预测
            </Link>

            <Link
              href="/pricing"
              className={`text-sm font-medium transition-colors ${
                isActive("/pricing")
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              定价
            </Link>
          </nav>

          {/* 右侧用户区域 */}
          <div className="flex items-center">
            {user ? (
              <div className="relative">
                <button
                  onClick={() => setShowMenu(!showMenu)}
                  className="h-10 w-10 rounded-full overflow-hidden border-2 border-primary/20 hover:border-primary/40 transition-all"
                >
                  <UserAvatar name={user.name} avatar={user.avatar} size="md" />
                </button>

                {showMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setShowMenu(false)}
                    />
                    <div className="absolute right-0 mt-2 w-40 bg-white rounded-xl shadow-lg border border-border py-1 z-20 backdrop-blur-xl">
                      <Link
                        href="/account"
                        onClick={() => setShowMenu(false)}
                        className="block w-full text-left px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
                      >
                        账户管理
                      </Link>
                      <button
                        onClick={() => {
                          logout();
                          setShowMenu(false);
                        }}
                        className="w-full text-left px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
                      >
                        登出
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <button
                onClick={() => setShowLoginModal(true)}
                className="px-6 py-2 rounded-full bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all active:scale-95"
              >
                登录
              </button>
            )}
          </div>
        </div>
      </header>

      <LoginModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} />
    </>
  );
}
