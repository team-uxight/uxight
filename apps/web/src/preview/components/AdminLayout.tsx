import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import {
  Bell,
  ChevronDown,
  LogOut,
  Menu,
  Monitor,
  Search,
  Settings,
  UserCircle,
  X,
} from "lucide-react";

import BrandLogo from "./BrandLogo";

import {
  API_BASE_URL,
  apiErrorMessage,
  authenticatedFetch,
  clearAccessToken,
} from "../auth";

import "./AdminLayout.css";

type UserProfile = {
  name?: string;
  role?: string;
};

const adminNavigation = [
  {
    label: "계정·권한",
    path: "/admin/users",
    icon: UserCircle,
  },
  {
    label: "정책·자원",
    path: "/admin/resources",
    icon: Settings,
  },
  {
    label: "사용량·감사",
    path: "/admin/audit",
    icon: Monitor,
  },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  const isPreview = location.pathname.startsWith("/admin-preview");

  const [userName, setUserName] = useState(isPreview ? "이유진" : "관리자");
  const [searchQuery, setSearchQuery] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    if (isPreview) return;

    let active = true;

    async function loadUser() {
      try {
        const response = await authenticatedFetch(
          `${API_BASE_URL}/api/users/me`,
        );

        if (!response.ok) {
          throw new Error(
            await apiErrorMessage(
              response,
              "사용자 정보를 불러오지 못했습니다.",
            ),
          );
        }

        const user = (await response.json()) as UserProfile;

        if (active && user.name) {
          setUserName(user.name);
        }
      } catch (error) {
        if (active) {
          setNotice(
            error instanceof Error
              ? error.message
              : "사용자 정보를 불러오지 못했습니다.",
          );
        }
      }
    }

    void loadUser();

    return () => {
      active = false;
    };
  }, [isPreview]);

  async function handleLogout() {
    if (isPreview) {
      setNotice("디자인 미리보기에서는 로그아웃이 필요하지 않습니다.");
      return;
    }

    if (isLoggingOut) return;

    setIsLoggingOut(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(response, "로그아웃에 실패했습니다."),
        );
      }

      clearAccessToken();
      localStorage.removeItem("userRole");

      navigate("/login", { replace: true });
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "로그아웃 중 오류가 발생했습니다.",
      );
    } finally {
      setIsLoggingOut(false);
    }
  }

  const today = new Date();

  const dateLabel = new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(today);

  return (
    <div className="admin-layout">
      {isSidebarOpen && (
        <button
          type="button"
          className="admin-sidebar-overlay"
          aria-label="메뉴 닫기"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* 왼쪽 사이드바 */}
      <aside
        className={`admin-sidebar ${isSidebarOpen ? "is-open" : ""}`}
        aria-label="관리자 메뉴"
      >
        <div className="admin-sidebar-logo">
          <NavLink
            to={isPreview ? "/admin-preview" : "/admin/users"}
            className="admin-logo-link"
            aria-label="UXight 관리자 홈"
            onClick={() => setIsSidebarOpen(false)}
          >
            <BrandLogo variant="light-bg" size="nav" />
          </NavLink>

          <button
            type="button"
            className="admin-sidebar-close"
            aria-label="사이드바 닫기"
            onClick={() => setIsSidebarOpen(false)}
          >
            <X size={20} />
          </button>
        </div>

        <nav className="admin-sidebar-nav">
          {adminNavigation.map((item) => {
            const Icon = item.icon;

            const targetPath = isPreview
              ? item.path === "/admin/users"
                ? "/admin-preview"
                : item.path === "/admin/resources"
                  ? "/admin-preview/resources"
                  : "/admin-preview/audit"
              : item.path;

            const isActive = location.pathname === targetPath;

            return (
              <NavLink
                key={item.path}
                to={targetPath}
                onClick={() => setIsSidebarOpen(false)}
                className={`admin-nav-item ${
                  isActive ? "admin-nav-active" : ""
                }`}
              >
                <Icon size={24} strokeWidth={1.8} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="admin-sidebar-bottom">
          <button
            type="button"
            className="admin-bottom-item"
            onClick={() => setNotice("알림 기능은 준비 중입니다.")}
          >
            <Bell size={24} strokeWidth={1.8} />
            <span>알림</span>
          </button>

          <button
            type="button"
            className="admin-bottom-item"
            onClick={() => void handleLogout()}
            disabled={isLoggingOut}
          >
            <LogOut size={24} strokeWidth={1.8} />
            <span>{isLoggingOut ? "로그아웃 중..." : "로그아웃"}</span>
          </button>
        </div>
      </aside>

      {/* 오른쪽 메인 화면 */}
      <div className="admin-main">
        <header className="admin-header">
          <button
            type="button"
            className="admin-mobile-menu"
            aria-label="메뉴 열기"
            onClick={() => setIsSidebarOpen(true)}
          >
            <Menu size={24} />
          </button>

          <div className="admin-header-search">
            <Search size={20} strokeWidth={1.8} />

            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="워크스페이스 내 검색"
              aria-label="워크스페이스 내 검색"
            />
          </div>

          <div className="admin-header-date">
            <time dateTime={today.toISOString().slice(0, 10)}>
              Today, {dateLabel}
            </time>
          </div>

          <div className="admin-header-profile">
            <div className="admin-profile-avatar">{userName.charAt(0)}</div>

            <span className="admin-profile-name">{userName}</span>

            <ChevronDown
              size={16}
              className="admin-profile-chevron"
              aria-hidden="true"
            />
          </div>
        </header>

        {notice && (
          <div className="admin-notice" role="status">
            <span>{notice}</span>

            <button
              type="button"
              aria-label="메시지 닫기"
              onClick={() => setNotice("")}
            >
              <X size={16} />
            </button>
          </div>
        )}

        <main className="admin-content">
          <Outlet context={{ userName, searchQuery }} />
        </main>
      </div>
    </div>
  );
}
