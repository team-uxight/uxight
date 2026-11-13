import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

type LocationState = { friction?: string };

const suggestions = [
  {
    id: "GACA-1234",
    title: "메뉴 탐색 배치",
    detail: "장학금 메뉴를 학사 메뉴 상단에 배치합니다.",
  },
  {
    id: "GACA-1235",
    title: "메뉴 라벨 변경",
    detail: "“장학 안내”를 “장학금 신청·안내”로 명확하게 바꿉니다.",
  },
  {
    id: "GACA-1236",
    title: "도움말 추가",
    detail: "신청 자격과 다음 단계를 안내하는 도움말을 추가합니다.",
  },
];

export default function RFixes() {
  const navigate = useNavigate();
  const location = useLocation();
  const friction = (location.state as LocationState | null)?.friction;
  const [selected, setSelected] = useState(suggestions[0].id);
  const [decision, setDecision] = useState("");

  const selectedSuggestion =
    suggestions.find((suggestion) => suggestion.id === selected) ??
    suggestions[0];

  return (
    <section className="rd-fixes" aria-labelledby="fixes-title">
      <div className="rd-fixes-main">
        <div className="rd-report-title-row">
          <div className="rd-title-inline">
            <h1 id="fixes-title">Fixes</h1>
            <span>— 개선안</span>
          </div>
          <button
            type="button"
            className="rd-run-chip"
            onClick={() => navigate("/reports")}
          >
            실험 13
          </button>
        </div>
        {friction && (
          <p className="rd-fixes-context">
            진단 항목: <strong>{friction}</strong>
          </p>
        )}

        {decision && (
          <p className="rd-inline-notice" role="status">
            {decision} — 실제 반영이나 재실험은 아직 연결되지 않았습니다.
          </p>
        )}

        <div className="rd-fixes-actions">
          <button
            className="rd-dark-pill"
            type="button"
            onClick={() => setDecision("개선안 승인")}
          >
            승인 및 재실험
          </button>
          <span />

          <button
            className="rd-pill-button"
            type="button"
            onClick={() => setDecision("개선안을 반려했습니다")}
          >
            반려
          </button>
        </div>
      </div>
      <aside className="rd-suggestion-panel" aria-label="개선안 목록">
        <h2>개선안 목록</h2>
        {suggestions.map((suggestion) => (
          <button
            className={`rd-suggestion-card${selected === suggestion.id ? " is-selected" : ""}`}
            type="button"
            key={suggestion.id}
            onClick={() => {
              setSelected(suggestion.id);
              setDecision("");
            }}
          >
            <span className="rd-suggestion-id">{suggestion.id}</span>
            <span className="rd-suggestion-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path d="M7 5.5h12M7 10h12M7 14.5h12M7 19h12" />
                <circle cx="4" cy="5.5" r=".75" />
                <circle cx="4" cy="10" r=".75" />
                <circle cx="4" cy="14.5" r=".75" />
                <circle cx="4" cy="19" r=".75" />
              </svg>
            </span>
            <strong>{suggestion.title}</strong>
            <small>{suggestion.detail}</small>
            <span className="rd-suggestion-chevron" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path d="m6 9 6 6 6-6" />
              </svg>
            </span>
          </button>
        ))}
        <p className="rd-suggestion-selected">
          선택됨: {selectedSuggestion.title}
        </p>
      </aside>
    </section>
  );
}
