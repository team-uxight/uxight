import { useMemo, useState } from "react";
import {
  ChevronDown,
  Download,
  ArrowUpRight,
  AlertTriangle,
  Check,
  X,
} from "lucide-react";
import "./AdminAudit.css";

type RunStatus = "완료" | "실행 중" | "오류" | "차단됨";

type Run = {
  id: string;
  user: string;
  date: string;
  target: string;
  cost: number;
  status: RunStatus;
};

type AuditLog = {
  title: string;
  description: string;
  type: "warning" | "success";
};

const DAILY_COSTS = [
  25000, 40000, 20000, 50000, 35000, 60000, 45000, 65000, 55000, 40000, 50000,
  60000, 70000, 65000, 75000, 70000, 80000, 75000, 80000, 70000, 110000,
];

const RECENT_RUNS: Run[] = [
  {
    id: "RUN-021",
    user: "김리서처",
    date: "2026.09.21 14:30",
    target: "수강신청 시스템",
    cost: 45000,
    status: "완료",
  },
  {
    id: "RUN-020",
    user: "이리서처",
    date: "2026.09.21 13:05",
    target: "가천대 포털",
    cost: 32000,
    status: "완료",
  },
  {
    id: "RUN-019",
    user: "박리서처",
    date: "2026.09.21 11:42",
    target: "장애 개선 시나리오",
    cost: 18000,
    status: "오류",
  },
];

const AUDIT_LOGS: AuditLog[] = [
  {
    title: "도메인 이탈 차단 · RUN-019",
    description: "정도전 · 2026.09.20 18:55",
    type: "warning",
  },
  {
    title: "파괴적 클릭 차단 · RUN-018",
    description: "김유신 · 2026.09.20 17:12",
    type: "warning",
  },
  {
    title: "한도 초과 차단 · RUN-017",
    description: "홍길동 · 2026.09.20 15:40",
    type: "warning",
  },
  {
    title: "RUN-020 실행 승인",
    description: "운영자 김관리 · 2026.09.20 14:10",
    type: "success",
  },
];

const STATUS_COUNTS = [
  { label: "완료", count: 216 },
  { label: "실행 중", count: 32 },
  { label: "오류", count: 12 },
  { label: "차단됨", count: 8 },
];

const won = (value: number) => `₩ ${value.toLocaleString("ko-KR")}`;

export default function AdminAudit() {
  const [period, setPeriod] = useState("2026-09-01");
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [notice, setNotice] = useState("");

  const stats = [
    {
      label: "이번 달 비용",
      value: "₩ 1,240,000",
      note: "runs 비용 합계 · 9월 1일–21일",
    },
    {
      label: "사용 토큰",
      value: "12,480",
      note: "이번 달 누적 토큰 · runs 파생값",
    },
    {
      label: "run 수",
      value: "268",
      note: "완료 216 · 실행 중 32 · 오류 12 · 차단 8",
    },
    {
      label: "실행 중",
      value: "32",
      note: "정책 상한 100 (예시) · 32% 사용",
    },
  ];

  const selectedRunData = useMemo(
    () => RECENT_RUNS.find((run) => run.id === selectedRun),
    [selectedRun],
  );

  function exportAuditLogs() {
    const rows = [
      ["이벤트", "상세", "유형"],
      ...AUDIT_LOGS.map((log) => [
        log.title,
        log.description,
        log.type === "warning" ? "경고" : "성공",
      ]),
    ];

    const csv = rows
      .map((row) =>
        row.map((value) => `"${value.replace(/"/g, '""')}"`).join(","),
      )
      .join("\r\n");

    const blob = new Blob(["\uFEFF", csv], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "uxight-audit-preview.csv";
    link.click();
    URL.revokeObjectURL(url);
    setNotice("예시 감사 로그 CSV를 내보냈습니다.");
  }

  return (
    <div className="admin-audit">
      {/* 페이지 제목 */}
      <header className="admin-audit-heading">
        <div>
          <h1>사용량·감사</h1>
          <p>운영자 홈 · P2 / S2 와이어프레임 · 예시 데이터</p>
        </div>

        <div className="admin-audit-actions">
          <label className="admin-audit-period">
            <select
              value={period}
              onChange={(event) => {
                setPeriod(event.target.value);
                setNotice(
                  "현재 그래프와 통계는 9월 1일–21일 고정 예시 데이터입니다.",
                );
              }}
              aria-label="조회 기간"
            >
              <option value="2026-09-01">2026.09.01 ~ 09.21 · 필터</option>
              <option value="2026-09-08">2026.09.08 ~ 09.21 · 필터</option>
              <option value="2026-09-15">2026.09.15 ~ 09.21 · 필터</option>
            </select>
            <ChevronDown size={16} />
          </label>

          <button
            type="button"
            className="admin-audit-export"
            onClick={exportAuditLogs}
          >
            <Download size={15} />
            로그 내보내기 · P2
          </button>
        </div>
      </header>

      {notice && (
        <div className="admin-audit-notice" role="status">
          {notice}
          <button
            type="button"
            onClick={() => setNotice("")}
            aria-label="알림 닫기"
          >
            <X size={15} />
          </button>
        </div>
      )}

      {/* 지표 카드 4개 */}
      <div className="admin-audit-stats">
        {stats.map((stat) => (
          <section className="admin-audit-stat" key={stat.label}>
            <h2>{stat.label}</h2>
            <strong>{stat.value}</strong>
            <p>{stat.note}</p>
          </section>
        ))}
      </div>

      {/* 그래프와 상태 */}
      <div className="admin-audit-grid">
        <section className="admin-audit-panel admin-audit-chart-panel">
          <div className="admin-audit-panel-title">
            <h2>일별 비용</h2>
            <span>예시 · 9월 1일–21일</span>
          </div>

          <div
            className="admin-audit-chart"
            role="img"
            aria-label="9월 1일부터 21일까지의 일별 비용 막대그래프"
          >
            {DAILY_COSTS.map((cost, index) => (
              <div className="admin-audit-chart-day" key={index}>
                <div className="admin-audit-bar-area">
                  <div
                    className="admin-audit-bar"
                    style={{
                      height: `${(cost / 110000) * 100}%`,
                    }}
                    title={`${index + 1}일 · ${won(cost)}`}
                  />
                </div>
                <span>{index + 1}일</span>
              </div>
            ))}
          </div>

          <p className="admin-audit-chart-note">
            일별 비용(원) · 최대 ₩110,000 · 기간 합계 ₩1,240,000
          </p>
        </section>

        <section className="admin-audit-panel admin-audit-status-panel">
          <h2>상태</h2>
          <div className="admin-audit-status-list">
            {STATUS_COUNTS.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <strong>{item.count}</strong>
              </div>
            ))}
          </div>

          <div className="admin-audit-info">
            <strong>비고</strong>
            <p>
              차단된 행동은 도메인 이탈, 파괴적 클릭, 한도 초과 기준으로
              집계됩니다.
            </p>
          </div>
        </section>

        {/* 최근 run */}
        <section className="admin-audit-panel admin-audit-runs-panel">
          <div className="admin-audit-panel-title">
            <h2>최근 run</h2>
            <button
              type="button"
              className="admin-audit-open-run"
              disabled={!selectedRunData}
              onClick={() => {
                if (selectedRunData) {
                  setNotice(
                    `${selectedRunData.id} 상세 화면은 아직 연결되지 않았습니다.`,
                  );
                }
              }}
            >
              선택 run 열기
              <ArrowUpRight size={16} />
            </button>
          </div>

          <div className="admin-audit-table-scroll">
            <table className="admin-audit-run-table">
              <thead>
                <tr>
                  <th>누가</th>
                  <th>언제</th>
                  <th>대상</th>
                  <th>비용</th>
                  <th>상태</th>
                </tr>
              </thead>
              <tbody>
                {RECENT_RUNS.map((run) => (
                  <tr
                    key={run.id}
                    onClick={() => setSelectedRun(run.id)}
                    className={selectedRun === run.id ? "is-selected" : ""}
                    aria-selected={selectedRun === run.id}
                  >
                    <td>{run.user}</td>
                    <td>{run.date}</td>
                    <td>{run.target}</td>
                    <td>{won(run.cost)}</td>
                    <td>
                      <span
                        className={`admin-audit-status-badge ${
                          run.status === "완료" ? "complete" : "error"
                        }`}
                      >
                        {run.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* 감사 로그 */}
        <section className="admin-audit-panel admin-audit-logs-panel">
          <div className="admin-audit-panel-title">
            <h2>감사 로그</h2>
            <span>audit_log · D18</span>
          </div>

          <div className="admin-audit-log-list">
            {AUDIT_LOGS.map((log, index) => (
              <div className="admin-audit-log" key={index}>
                <div className={`admin-audit-log-icon ${log.type}`}>
                  {log.type === "warning" ? (
                    <AlertTriangle size={16} />
                  ) : (
                    <Check size={16} />
                  )}
                </div>
                <div>
                  <strong>{log.title}</strong>
                  <p>{log.description}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
