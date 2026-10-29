import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import "./AdminStopModal.css";

interface AdminStopModalProps {
  onClose: () => void;
  onConfirm: () => void;
}

export default function AdminStopModal({
  onClose,
  onConfirm,
}: AdminStopModalProps) {
  const [step, setStep] = useState<1 | 2>(1);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("keydown", handleEscape);
    };
  }, [onClose]);

  function handleConfirm() {
    if (!checked || step !== 2) return;

    onConfirm();
  }

  return (
    <div
      className="admin-stop-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        className="admin-stop-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="admin-stop-title"
      >
        {/* 경고 아이콘 */}
        <div className="admin-stop-icon">
          <AlertTriangle size={24} strokeWidth={1.8} />
        </div>

        {/* 제목 */}
        <h2 id="admin-stop-title">
          {step === 1
            ? "전체 실험을 중단할까요?"
            : "전체 실험 중단 · 최종 확인"}
        </h2>

        {/* 단계 표시 */}
        <div className="admin-stop-steps">
          <span className={step === 1 ? "active" : ""}>1단계 · 실행 확인</span>

          <span className={step === 2 ? "active" : ""}>2단계 · 최종 확인</span>
        </div>

        {step === 1 ? (
          <>
            {/* 1단계 설명 */}
            <p className="admin-stop-description">
              진행 중인 모든 실험에 중단을 요청합니다. 한 번 시작한 중단 작업은
              되돌릴 수 없어요.
            </p>

            {/* 위험 안내 */}
            <div className="admin-stop-risk">
              <strong>중단 전에 확인해 주세요</strong>
              <p>• 실행 중인 모든 실험이 영향을 받습니다.</p>
              <p>• 이미 수집한 실험 결과는 삭제되지 않습니다.</p>
              <p>• 완료까지 최대 10초가 소요될 수 있습니다.</p>
            </div>

            {/* 1단계 버튼 */}
            <div className="admin-stop-actions">
              <button
                type="button"
                className="admin-stop-cancel"
                onClick={onClose}
              >
                취소
              </button>

              <button
                type="button"
                className="admin-stop-danger"
                onClick={() => setStep(2)}
              >
                다음 · 최종 확인 →
              </button>
            </div>
          </>
        ) : (
          <>
            {/* 2단계 설명 */}
            <p className="admin-stop-description">
              정말 전체 실험을 중단하시겠습니까? 아래 항목에 체크하면 최종 중단
              버튼이 활성화됩니다.
            </p>

            {/* 최종 위험 안내 */}
            <div className="admin-stop-risk final">
              <p>⚠ 모든 실행 중인 실험이 중단 대상입니다.</p>
              <p>이 작업은 감사 로그에 기록됩니다.</p>
            </div>

            {/* 체크박스 */}
            <label className="admin-stop-check">
              <input
                type="checkbox"
                checked={checked}
                onChange={(event) => setChecked(event.target.checked)}
              />
              <span>전체 실험 중단의 영향을 확인했습니다.</span>
            </label>

            {/* 2단계 버튼 */}
            <div className="admin-stop-actions">
              <button
                type="button"
                className="admin-stop-cancel"
                onClick={() => setStep(1)}
              >
                이전
              </button>

              <button
                type="button"
                className="admin-stop-danger"
                disabled={!checked}
                onClick={handleConfirm}
              >
                모든 실험 중단
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
