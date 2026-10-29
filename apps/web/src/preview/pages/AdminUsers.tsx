import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  MoreHorizontal,
  Plus,
  RefreshCw,
  Search,
  X,
  Users,
  UserCheck,
  ShieldCheck,
  UserX,
} from "lucide-react";

import { API_BASE_URL, apiErrorMessage, authenticatedFetch } from "../auth";

import AdminUserModal from "../components/AdminUserModal";
import "./AdminUsers.css";

// ==========================================
// 타입 정의
// ==========================================

type UserRole = "admin" | "maintainer" | "researcher";
type AuthProvider = "local" | "google";
type StatusFilter = "all" | "active" | "inactive";

interface AdminUser {
  userId: number;
  email: string;
  name: string;
  role: UserRole;
  authProvider: AuthProvider;
  isActive: boolean;
  createdAt: string;
}

interface UserPage {
  content: AdminUser[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
}

type UserAction =
  | {
      type: "role";
      user: AdminUser;
      newRole: UserRole;
    }
  | {
      type: "active";
      user: AdminUser;
      newActive: boolean;
    };

const PAGE_SIZE = 20;

const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  maintainer: "Maintainer",
  researcher: "Researcher",
};

// ==========================================
// 미리보기용 예시 데이터
// ==========================================

const PREVIEW_USERS: AdminUser[] = [
  {
    userId: 1,
    name: "김민지",
    email: "minji@uxight.ai",
    role: "admin",
    authProvider: "local",
    isActive: true,
    createdAt: "2026-10-01",
  },
  {
    userId: 2,
    name: "이준호",
    email: "junho@uxight.ai",
    role: "maintainer",
    authProvider: "google",
    isActive: true,
    createdAt: "2026-10-03",
  },
  {
    userId: 3,
    name: "박서연",
    email: "seoyeon@uxight.ai",
    role: "researcher",
    authProvider: "local",
    isActive: false,
    createdAt: "2026-10-05",
  },
  {
    userId: 4,
    name: "최지훈",
    email: "jihoon@uxight.ai",
    role: "researcher",
    authProvider: "google",
    isActive: true,
    createdAt: "2026-10-07",
  },
  {
    userId: 5,
    name: "정하늘",
    email: "haneul@uxight.ai",
    role: "researcher",
    authProvider: "local",
    isActive: true,
    createdAt: "2026-10-09",
  },
  {
    userId: 6,
    name: "강서준",
    email: "seojun@uxight.ai",
    role: "researcher",
    authProvider: "google",
    isActive: false,
    createdAt: "2026-10-11",
  },
  {
    userId: 7,
    name: "오지은",
    email: "jieun@uxight.ai",
    role: "maintainer",
    authProvider: "local",
    isActive: true,
    createdAt: "2026-10-13",
  },
  {
    userId: 8,
    name: "윤도현",
    email: "dohyun@uxight.ai",
    role: "researcher",
    authProvider: "google",
    isActive: true,
    createdAt: "2026-10-15",
  },
];

// ==========================================
// 계정·권한 페이지
// ==========================================

export default function AdminUsers() {
  const location = useLocation();

  const isPreview = location.pathname.startsWith("/admin-preview");

  // 사용자 목록
  const [users, setUsers] = useState<AdminUser[]>(
    isPreview ? [...PREVIEW_USERS] : [],
  );

  // 페이지 정보
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(isPreview ? 1 : 0);
  const [totalElements, setTotalElements] = useState(
    isPreview ? PREVIEW_USERS.length : 0,
  );

  // 검색 및 필터
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRole | "all">("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  // 로그인한 사용자 권한
  const [myRole, setMyRole] = useState<UserRole | null>(
    isPreview ? "admin" : null,
  );

  // 로딩 및 메시지
  const [loading, setLoading] = useState(!isPreview);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // 개인별 계정 관리 팝업
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  const selectedUser = users.find((user) => user.userId === selectedUserId);

  // 계정 변경 확인 팝업
  const [pendingAction, setPendingAction] = useState<UserAction | null>(null);

  // ==========================================
  // 계정 현황
  // ==========================================

  const activeCount = users.filter((user) => user.isActive).length;

  const operatorCount = users.filter(
    (user) => user.role === "admin" || user.role === "maintainer",
  ).length;

  const inactiveCount = users.filter((user) => !user.isActive).length;

  const accountStats = [
    {
      label: "전체 사용자",
      value: totalElements,
      note: "등록된 모든 계정",
      icon: Users,
    },
    {
      label: "활성 계정",
      value: activeCount,
      note: "로그인 가능한 계정",
      icon: UserCheck,
    },
    {
      label: "운영자 계정",
      value: operatorCount,
      note: "Admin + Maintainer",
      icon: ShieldCheck,
    },
    {
      label: "비활성 계정",
      value: inactiveCount,
      note: "접근이 제한된 계정",
      icon: UserX,
    },
  ];

  // ==========================================
  // 사용자 목록 조회
  // ==========================================

  const loadUsers = useCallback(async () => {
    // 디자인 미리보기
    if (isPreview) {
      setUsers([...PREVIEW_USERS]);
      setTotalPages(1);
      setTotalElements(PREVIEW_USERS.length);
      setLoading(false);
      setError("");
      return;
    }

    // 실제 백엔드 데이터 조회
    setLoading(true);
    setError("");

    try {
      const response = await authenticatedFetch(
        `${API_BASE_URL}/api/admin/users?page=${page}&size=${PAGE_SIZE}`,
      );

      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(response, "사용자 목록을 불러오지 못했습니다."),
        );
      }

      const data = (await response.json()) as UserPage;

      if (
        !Array.isArray(data.content) ||
        typeof data.totalPages !== "number" ||
        typeof data.totalElements !== "number"
      ) {
        throw new Error("사용자 목록 응답 형식이 올바르지 않습니다.");
      }

      setUsers(data.content);
      setTotalPages(data.totalPages);
      setTotalElements(data.totalElements);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "사용자 목록을 불러오지 못했습니다.",
      );
    } finally {
      setLoading(false);
    }
  }, [page, isPreview]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  // ==========================================
  // 로그인 사용자 역할 조회
  // ==========================================

  useEffect(() => {
    if (isPreview) return;

    let active = true;

    async function loadMe() {
      try {
        const response = await authenticatedFetch(
          `${API_BASE_URL}/api/users/me`,
        );

        if (!response.ok) return;

        const data = (await response.json()) as {
          role?: UserRole;
        };

        if (active && data.role) {
          setMyRole(data.role);
        }
      } catch {
        // 인증과 권한은 ProtectedRoute와 BE에서도 확인
      }
    }

    void loadMe();

    return () => {
      active = false;
    };
  }, [isPreview]);

  // ==========================================
  // 검색 및 필터
  // ==========================================

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();

    return users.filter((user) => {
      const matchesSearch =
        user.name.toLowerCase().includes(query) ||
        user.email.toLowerCase().includes(query);

      const matchesRole = roleFilter === "all" || user.role === roleFilter;

      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" ? user.isActive : !user.isActive);

      return matchesSearch && matchesRole && matchesStatus;
    });
  }, [users, search, roleFilter, statusFilter]);

  function resetFilters() {
    setSearch("");
    setRoleFilter("all");
    setStatusFilter("all");
  }

  // ==========================================
  // 관리 권한 확인
  // ==========================================

  function canManageUser(user: AdminUser): boolean {
    if (myRole === "admin") return true;

    return myRole === "maintainer" && user.role === "researcher";
  }

  // ==========================================
  // 개인별 계정 관리 팝업
  // ==========================================

  function openUserModal(user: AdminUser) {
    setSelectedUserId(user.userId);
  }

  function closeUserModal() {
    setSelectedUserId(null);
  }

  function requestRoleChange(user: AdminUser, newRole: UserRole) {
    if (user.role === newRole) return;

    setSelectedUserId(null);

    setPendingAction({
      type: "role",
      user,
      newRole,
    });
  }

  function requestActiveChange(user: AdminUser) {
    setSelectedUserId(null);

    setPendingAction({
      type: "active",
      user,
      newActive: !user.isActive,
    });
  }

  // ==========================================
  // 계정 변경 처리
  // ==========================================

  async function confirmAction() {
    if (!pendingAction || saving) return;

    const action = pendingAction;
    const { user } = action;
    const isRoleChange = action.type === "role";

    // 미리보기에서는 화면 데이터만 변경
    if (isPreview) {
      setUsers((prev) =>
        prev.map((item) => {
          if (item.userId !== user.userId) {
            return item;
          }

          if (action.type === "role") {
            return {
              ...item,
              role: action.newRole,
            };
          }

          return {
            ...item,
            isActive: action.newActive,
          };
        }),
      );

      setPendingAction(null);
      setNotice("미리보기 데이터에만 변경 사항을 적용했습니다.");
      return;
    }

    // 실제 백엔드 API 요청
    setSaving(true);
    setError("");

    try {
      const url = isRoleChange
        ? `${API_BASE_URL}/api/admin/users/${user.userId}/role`
        : `${API_BASE_URL}/api/admin/users/${user.userId}/active`;

      const body =
        action.type === "role"
          ? { role: action.newRole }
          : { isActive: action.newActive };

      const response = await authenticatedFetch(url, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(response, "계정 정보를 변경하지 못했습니다."),
        );
      }

      setNotice(`${user.name}님의 계정 정보가 변경되었습니다.`);

      setPendingAction(null);
      setSelectedUserId(null);

      await loadUsers();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "변경 요청 중 오류가 발생했습니다.",
      );
    } finally {
      setSaving(false);
    }
  }

  // ==========================================
  // 페이지 화면
  // ==========================================

  return (
    <div className="admin-users">
      {/* 페이지 제목 */}
      <div className="admin-users-heading">
        <div className="admin-users-heading-text">
          <h1>계정·권한</h1>
          <p>
            {isPreview ? "리서처 계정 관리 / 예시 데이터" : "리서처 계정 관리"}
          </p>
        </div>

        <div className="admin-users-actions">
          <button
            type="button"
            className="admin-users-btn admin-users-btn-secondary"
            onClick={() => void loadUsers()}
            disabled={loading}
          >
            <RefreshCw size={15} />
            새로고침
          </button>

          <button
            type="button"
            className="admin-users-btn admin-users-btn-primary"
            onClick={() =>
              setNotice("계정 추가 기능은 아직 연결되지 않았습니다.")
            }
          >
            <Plus size={16} />
            계정 추가
          </button>
        </div>
      </div>

      {/* 알림 */}
      {notice && (
        <div className="admin-users-notice" role="status">
          <span>{notice}</span>

          <button
            type="button"
            aria-label="알림 닫기"
            onClick={() => setNotice("")}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* 오류 메시지 */}
      {error && (
        <div className="admin-users-error" role="alert">
          {error}
        </div>
      )}

      {/* ======================================
          계정 현황 카드 4개
      ====================================== */}

      <div className="admin-users-stats">
        {accountStats.map((stat) => {
          const Icon = stat.icon;

          return (
            <section key={stat.label} className="admin-users-stat-card">
              <div className="admin-users-stat-label">{stat.label}</div>

              <div className="admin-users-stat-value">{stat.value}</div>

              <div className="admin-users-stat-note">{stat.note}</div>

              <div className="admin-users-stat-icon">
                <Icon size={20} strokeWidth={1.8} />
              </div>
            </section>
          );
        })}
      </div>

      {/* ======================================
          사용자 목록
      ====================================== */}

      <section className="admin-users-panel">
        {/* 사용자 목록 제목 */}
        <div className="admin-users-panel-head">
          <div>
            <h2>사용자 목록</h2>
            <p>계정 정보, 역할 및 접근 상태를 확인하거나 변경할 수 있습니다.</p>
          </div>

          <span className="admin-users-count">{totalElements} accounts</span>
        </div>

        {/* 검색 및 필터 */}
        <div className="admin-users-filters">
          <label className="admin-users-search">
            <Search size={18} />

            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="이름 또는 이메일로 검색"
              aria-label="이름 또는 이메일로 검색"
            />
          </label>

          <select
            className="admin-users-select"
            value={roleFilter}
            onChange={(event) =>
              setRoleFilter(event.target.value as UserRole | "all")
            }
            aria-label="역할 필터"
          >
            <option value="all">모든 역할</option>
            <option value="admin">Admin</option>
            <option value="maintainer">Maintainer</option>
            <option value="researcher">Researcher</option>
          </select>

          <select
            className="admin-users-select"
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value as StatusFilter)
            }
            aria-label="상태 필터"
          >
            <option value="all">모든 상태</option>
            <option value="active">활성</option>
            <option value="inactive">비활성</option>
          </select>

          <button
            type="button"
            className="admin-users-btn admin-users-btn-secondary"
            onClick={resetFilters}
          >
            필터 초기화
          </button>
        </div>

        {/* ==================================
            사용자 테이블
        ================================== */}

        <div className="admin-users-table-wrap">
          <table className="admin-users-table">
            <thead>
              <tr>
                <th>이름</th>
                <th>이메일</th>
                <th>역할</th>
                <th>상태</th>
                <th>가입 경로</th>
                <th>마지막 로그인</th>
                <th>누적 비용</th>
                <th>관리</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="admin-users-empty">
                    사용자 목록을 불러오는 중입니다.
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={8} className="admin-users-empty">
                    표시할 사용자 계정이 없습니다.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((user) => (
                  <tr key={user.userId}>
                    {/* 이름 */}
                    <td>
                      <div className="admin-users-name-cell">
                        <span className="admin-users-avatar">
                          {user.name.charAt(0) || "?"}
                        </span>

                        <strong>{user.name}</strong>
                      </div>
                    </td>

                    {/* 이메일 */}
                    <td>{user.email}</td>

                    {/* 역할 */}
                    <td>
                      <span
                        className={`admin-users-role admin-users-role-${user.role}`}
                      >
                        {ROLE_LABELS[user.role]}
                      </span>
                    </td>

                    {/* 상태 */}
                    <td>
                      <span
                        className={`admin-users-status ${
                          user.isActive ? "is-active" : "is-inactive"
                        }`}
                      >
                        ● {user.isActive ? "활성" : "비활성"}
                      </span>
                    </td>

                    {/* 가입 경로 */}
                    <td>
                      {user.authProvider === "google" ? "Google" : "이메일"}
                    </td>

                    {/* 마지막 로그인 */}
                    <td className="admin-users-muted">—</td>

                    {/* 누적 비용 */}
                    <td className="admin-users-muted">—</td>

                    {/* 계정 관리 버튼 */}
                    <td className="admin-users-manage-cell">
                      <button
                        type="button"
                        className="admin-users-menu-trigger"
                        aria-label={`${user.name} 계정 관리`}
                        disabled={!canManageUser(user)}
                        onClick={() => openUserModal(user)}
                      >
                        <MoreHorizontal size={20} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 페이지 이동 */}
        <div className="admin-users-pagination">
          <span>
            전체 {totalElements}개 계정
            {isPreview
              ? " · 디자인 미리보기"
              : " · 현재 페이지에서 검색 및 필터 적용"}
          </span>

          <div>
            <button
              type="button"
              disabled={page === 0 || loading}
              onClick={() => setPage((prev) => Math.max(0, prev - 1))}
            >
              이전
            </button>

            <span>
              {totalPages === 0 ? 0 : page + 1}
              {" / "}
              {totalPages}
            </span>

            <button
              type="button"
              disabled={loading || page + 1 >= totalPages}
              onClick={() => setPage((prev) => prev + 1)}
            >
              다음
            </button>
          </div>
        </div>
      </section>

      {/* ======================================
          개인별 계정 관리 팝업
          AdminUserModal.tsx import 사용
      ====================================== */}

      {selectedUser && !pendingAction && (
        <AdminUserModal
          user={selectedUser}
          currentUserRole={myRole}
          onClose={closeUserModal}
          onChangeRole={(role) => requestRoleChange(selectedUser, role)}
          onChangeActive={() => requestActiveChange(selectedUser)}
          isLoading={saving}
        />
      )}

      {/* ======================================
          계정 변경 확인 모달
      ====================================== */}

      {pendingAction && (
        <div className="admin-users-modal-overlay">
          <div
            className="admin-users-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="admin-action-title"
          >
            <h2 id="admin-action-title">계정 정보 변경</h2>

            <p>
              <strong>{pendingAction.user.name}</strong>
              님의{" "}
              {pendingAction.type === "role"
                ? `역할을 ${ROLE_LABELS[pendingAction.newRole]}(으)로 변경`
                : pendingAction.newActive
                  ? "계정을 활성화"
                  : "계정을 비활성화"}
              하시겠습니까?
            </p>

            <div className="admin-users-modal-actions">
              <button
                type="button"
                className="admin-users-btn admin-users-btn-secondary"
                disabled={saving}
                onClick={() => setPendingAction(null)}
              >
                취소
              </button>

              <button
                type="button"
                className="admin-users-btn admin-users-btn-primary"
                disabled={saving}
                onClick={() => void confirmAction()}
              >
                {saving ? "처리 중..." : "변경하기"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
