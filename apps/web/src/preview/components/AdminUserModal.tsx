import { useEffect, useState } from "react";
import { UserRound } from "lucide-react";

import "./AdminUserModal.css";

// 사용자 역할
export type UserRole = "admin" | "maintainer" | "researcher";

// 팝업에 필요한 사용자 정보
export interface AdminUserModalData {
  userId: number;
  name: string;
  email: string;
  role: UserRole;
  isActive: boolean;
}

// 부모 컴포넌트에서 전달받는 값
interface AdminUserModalProps {
  user: AdminUserModalData;
  currentUserRole: UserRole | null;

  onClose: () => void;
  onChangeRole: (role: UserRole) => void;
  onChangeActive: () => void;

  isLoading?: boolean;
}

// 역할 표시 이름
const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  maintainer: "Maintainer",
  researcher: "Researcher",
};

const ROLE_OPTIONS: UserRole[] = ["admin", "maintainer", "researcher"];

export default function AdminUserModal({
  user,
  currentUserRole,
  onClose,
  onChangeRole,
  onChangeActive,
  isLoading = false,
}: AdminUserModalProps) {
  // 선택된 역할
  const [selectedRole, setSelectedRole] = useState<UserRole>(user.role);

  // 다른 사용자를 열면 역할 초기화
  useEffect(() => {
    setSelectedRole(user.role);
  }, [user.userId, user.role]);

  // ESC 키로 팝업 닫기
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !isLoading) {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose, isLoading]);

  // 현재 사용자의 관리 권한
  const canManage =
    currentUserRole === "admin" ||
    (currentUserRole === "maintainer" && user.role === "researcher");

  // 역할 변경 권한
  const canChangeRole =
    canManage &&
    selectedRole !== user.role &&
    (currentUserRole === "admin" || selectedRole === "researcher");

  // 비활성화/활성화 권한
  const canChangeActive = canManage && user.role === "researcher";

  function handleRoleChange() {
    if (!canChangeRole || isLoading) return;

    onChangeRole(selectedRole);
  }

  function handleActiveChange() {
    if (!canChangeActive || isLoading) return;

    onChangeActive();
  }

  return (
    <div
      className="admin-user-modal-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isLoading) {
          onClose();
        }
      }}
    >
      <div
        className="admin-user-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="admin-user-modal-title"
        aria-describedby="admin-user-modal-description"
      >
        {/* ==========================
            상단 아이콘
        ========================== */}
        <div className="admin-user-modal-icon">
          <UserRound size={24} strokeWidth={1.8} />
        </div>

        {/* ==========================
            제목 및 설명
        ========================== */}
        <h2 id="admin-user-modal-title" className="admin-user-modal-title">
          {user.name} 계정 관리
        </h2>

        <p
          id="admin-user-modal-description"
          className="admin-user-modal-description"
        >
          {user.email} · 계정의 역할과 접근 상태를 변경할 수 있습니다.
        </p>

        {/* ==========================
            현재 역할
        ========================== */}
        <div className="admin-user-modal-detail">
          <span>현재 역할</span>

          <strong>{ROLE_LABELS[user.role]}</strong>
        </div>

        {/* ==========================
            현재 상태
        ========================== */}
        <div className="admin-user-modal-detail">
          <span>현재 상태</span>

          <strong>{user.isActive ? "활성" : "비활성"}</strong>
        </div>

        {/* ==========================
            변경할 역할
        ========================== */}
        <div className="admin-user-modal-form">
          <label htmlFor="admin-modal-role">변경할 역할</label>

          <select
            id="admin-modal-role"
            value={selectedRole}
            disabled={!canManage || isLoading}
            onChange={(event) => {
              setSelectedRole(event.target.value as UserRole);
            }}
          >
            {ROLE_OPTIONS.filter(
              (role) => currentUserRole === "admin" || role === "researcher",
            ).map((role) => (
              <option key={role} value={role}>
                {ROLE_LABELS[role]}
              </option>
            ))}
          </select>
        </div>

        {/* ==========================
            하단 버튼
        ========================== */}
        <div className="admin-user-modal-actions">
          {/* 취소 */}
          <button
            type="button"
            className="admin-user-modal-cancel"
            disabled={isLoading}
            onClick={onClose}
          >
            취소
          </button>

          {/* 계정 상태 변경 */}
          <button
            type="button"
            className="admin-user-modal-danger"
            disabled={!canChangeActive || isLoading}
            onClick={handleActiveChange}
          >
            {user.isActive ? "비활성화" : "활성화"}
          </button>

          {/* 역할 변경 */}
          <button
            type="button"
            className="admin-user-modal-save"
            disabled={!canChangeRole || isLoading}
            onClick={handleRoleChange}
          >
            역할 변경
          </button>
        </div>
      </div>
    </div>
  );
}
